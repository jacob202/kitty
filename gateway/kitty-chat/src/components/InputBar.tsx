'use client'
import { useRef, useEffect, useState, KeyboardEvent, RefObject } from 'react'
import { Mic, Square, Paperclip, X, Zap } from 'lucide-react'
import { MessageAttachment, Model } from '@/lib/types'
import type { ContextCandidate, ContextReference, ContextReferenceKind } from '@/lib/context-references'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop?: () => void
  isStreaming?: boolean
  disabled?: boolean
  chatTitle?: string
  modelName?: string
  modelColor?: string
  tokenCount?: number
  maxTokens?: number
  textareaRef?: RefObject<HTMLTextAreaElement | null>
  compact?: boolean
  attachments?: MessageAttachment[]
  onAddFiles?: (files: FileList) => void
  onRemoveAttachment?: (id: string) => void
  contextCandidates?: ContextCandidate[]
  contextRefs?: ContextReference[]
  onAddContextRef?: (ref: ContextReference) => void
  onRemoveContextRef?: (kind: ContextReferenceKind, id: string) => void
  /** CR-07: model list + one-shot override for the next message only. */
  models?: Model[]
  overrideModel?: Model | null
  onOverrideModel?: (m: Model | null) => void
}

type RecState = 'idle' | 'recording' | 'transcribing'

function formatBytes(n?: number): string {
  if (n === undefined || Number.isNaN(n)) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function InputBar({
  value, onChange, onSend, onStop, isStreaming, disabled,
  textareaRef,
  compact = false,
  attachments = [],
  onAddFiles,
  onRemoveAttachment,
  contextCandidates = [],
  contextRefs = [],
  onAddContextRef,
  onRemoveContextRef,
  models = [],
  overrideModel = null,
  onOverrideModel,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const ref = textareaRef ?? internalRef
  const fileRef = useRef<HTMLInputElement>(null)

  const [recState, setRecState] = useState<RecState>('idle')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const [composerFocused, setComposerFocused] = useState(false)
  const [contextQuery, setContextQuery] = useState<string | null>(null)
  const [contextTriggerIndex, setContextTriggerIndex] = useState<number | null>(null)
  const [contextIndex, setContextIndex] = useState(0)
  const modelMenuRef = useRef<HTMLDivElement>(null)

  const selectedContextKeys = new Set(contextRefs.map((item) => `${item.kind}:${item.id}`))
  const filteredContextCandidates = contextQuery === null ? [] : contextCandidates
    .filter((item) => !selectedContextKeys.has(`${item.kind}:${item.id}`))
    .filter((item) => {
      const query = contextQuery.toLowerCase()
      return !query || item.label.toLowerCase().includes(query) || item.description?.toLowerCase().includes(query)
    })
    .slice(0, 8)
  const contextOpen = Boolean(onAddContextRef && contextQuery !== null && filteredContextCandidates.length > 0)

  useEffect(() => {
    if (!modelMenuOpen) return
    const close = (e: MouseEvent) => {
      if (!modelMenuRef.current?.contains(e.target as Node)) setModelMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [modelMenuOpen])

  useEffect(() => {
    if (!ref.current) return
    ref.current.style.height = 'auto'
    ref.current.style.height = Math.min(ref.current.scrollHeight, 200) + 'px'
  }, [value])

  useEffect(() => () => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
  }, [])

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
        await transcribeAndInsert(blob)
      }
      rec.start()
      recorderRef.current = rec
      setRecState('recording')
    } catch (err) {
      console.error('mic permission / start failed', err)
      setRecState('idle')
    }
  }

  function stopRecording() {
    const rec = recorderRef.current
    if (rec && rec.state !== 'inactive') {
      setRecState('transcribing')
      rec.stop()
    } else {
      setRecState('idle')
    }
  }

  async function transcribeAndInsert(blob: Blob) {
    try {
      const fd = new FormData()
      const ext = blob.type.includes('webm') ? 'webm' : blob.type.includes('ogg') ? 'ogg' : 'wav'
      fd.append('file', blob, `mic.${ext}`)
      fd.append('model', 'whisper-1')
      const res = await fetch('/proxy/v1/audio/transcriptions', { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Transcription HTTP ${res.status}`)
      const json = await res.json()
      const text = (json?.text ?? '').trim()
      if (text) {
        onChange(value ? `${value.trim()} ${text}` : text)
        ref.current?.focus()
      }
    } catch (err) {
      console.error('transcription failed', err)
    } finally {
      setRecState('idle')
      recorderRef.current = null
    }
  }

  const onMicClick = () => {
    if (recState === 'idle') void startRecording()
    else if (recState === 'recording') stopRecording()
  }

  const trackContextQuery = (next: string) => {
    const match = next.match(/(?:^|\s)@([^@\s]*)$/)
    if (!match) {
      setContextQuery(null)
      setContextTriggerIndex(null)
      setContextIndex(0)
      return
    }
    setContextQuery(match[1] ?? '')
    setContextTriggerIndex(next.lastIndexOf('@'))
    setContextIndex(0)
  }

  const selectContext = (candidate: ContextCandidate) => {
    if (!onAddContextRef || contextTriggerIndex === null) return
    const next = `${value.slice(0, contextTriggerIndex)}@${candidate.label} `
    onChange(next)
    onAddContextRef({ kind: candidate.kind, id: candidate.id, label: candidate.label })
    setContextQuery(null)
    setContextTriggerIndex(null)
    setContextIndex(0)
    window.setTimeout(() => ref.current?.focus(), 0)
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (contextOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setContextIndex((index) => (index + 1) % filteredContextCandidates.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setContextIndex((index) => (index - 1 + filteredContextCandidates.length) % filteredContextCandidates.length)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setContextQuery(null)
        setContextTriggerIndex(null)
        return
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        selectContext(filteredContextCandidates[contextIndex] ?? filteredContextCandidates[0])
        return
      }
    }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
      if (e.shiftKey) return
      e.preventDefault()
      if (!disabled && value.trim()) onSend()
    }
  }

  const onPickFiles = () => fileRef.current?.click()

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length && onAddFiles) onAddFiles(e.target.files)
    e.target.value = ''
  }

  const controlSize = compact ? 44 : 40

  return (
    <div style={{
      padding: compact ? '12px 12px calc(16px + env(safe-area-inset-bottom, 0px))' : '14px 26px 20px',
      flexShrink: 0,
      background: 'var(--bg)',
    }}>
      {contextRefs.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10, paddingLeft: 4 }}>
          {contextRefs.map((contextRef) => (
            <span key={`${contextRef.kind}:${contextRef.id}`} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              minHeight: 32, padding: '4px 7px 4px 10px', borderRadius: 999,
              border: '1px solid var(--color-separator)', background: 'var(--color-surface)',
              color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 11.5,
            }}>
              <span style={{ color: 'var(--color-text-secondary)', fontSize: 10 }}>{contextRef.kind}</span>
              <span>{contextRef.label}</span>
              {onRemoveContextRef && (
                <button
                  type="button"
                  aria-label={`Remove context ${contextRef.label}`}
                  onClick={() => onRemoveContextRef(contextRef.kind, contextRef.id)}
                  style={{ border: 'none', background: 'transparent', color: 'var(--color-text-secondary)', cursor: 'pointer', display: 'grid', placeItems: 'center', padding: 2 }}
                >
                  <X size={12} />
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {attachments.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: 10,
          paddingLeft: 4,
        }}>
          {attachments.map((att) => (
            <div key={att.id} style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              background: 'var(--surface)',
              border: '1.5px solid var(--line)',
              borderRadius: 10,
              padding: '5px 8px 5px 10px',
              maxWidth: 280,
            }}>
              <Paperclip size={12} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--ink)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {att.display_name}
                {att.size ? ` · ${formatBytes(att.size)}` : ''}
              </span>
              {onRemoveAttachment && (
                <button
                  type="button"
                  onClick={() => onRemoveAttachment(att.id)}
                  aria-label={`remove ${att.display_name}`}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: 'none', background: 'transparent', cursor: 'pointer',
                    color: 'var(--ink-2)', padding: 2, flexShrink: 0,
                  }}
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {onOverrideModel && overrideModel && (
        <div style={{ display: 'flex', marginBottom: 8, paddingLeft: 4 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: overrideModel.color,
            border: `1.5px solid ${overrideModel.color}`,
            borderRadius: 99, padding: '3px 10px',
          }}>
            <Zap size={10} />
            next message → {overrideModel.name}
            <button
              type="button"
              onClick={() => onOverrideModel(null)}
              aria-label="clear model override"
              style={{
                display: 'flex', border: 'none', background: 'transparent',
                color: 'inherit', cursor: 'pointer', padding: 0,
              }}
            >
              <X size={11} />
            </button>
          </span>
        </div>
      )}

      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: compact ? 4 : 6,
        background: 'var(--color-surface)',
        border: composerFocused ? '1px solid var(--color-accent)' : '1px solid var(--color-separator)',
        borderRadius: 18,
        padding: compact ? '7px 8px 7px 14px' : '9px 10px 9px 14px',
        boxShadow: composerFocused ? '0 0 0 3px var(--color-focus-ring)' : 'var(--shadow-soft)',
        maxWidth: compact ? '100%' : undefined,
        position: 'relative',
      }}>
        {contextOpen && (
          <div
            role="listbox"
            aria-label="Context suggestions"
            style={{
              position: 'absolute', left: 8, right: 8, bottom: 'calc(100% + 8px)', zIndex: 45,
              maxHeight: 280, overflowY: 'auto', padding: 6, borderRadius: 12,
              border: '1px solid var(--color-separator)', background: 'var(--color-surface)',
              boxShadow: 'var(--shadow)', display: 'grid', gap: 2,
            }}
          >
            {filteredContextCandidates.map((candidate, index) => (
              <button
                key={`${candidate.kind}:${candidate.id}`}
                type="button"
                role="option"
                aria-selected={index === contextIndex}
                aria-label={`${candidate.label} ${candidate.description ?? candidate.kind}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectContext(candidate)}
                style={{
                  border: 'none', borderRadius: 8, padding: '9px 10px', textAlign: 'left', cursor: 'pointer',
                  background: index === contextIndex ? 'var(--color-surface-elevated)' : 'transparent',
                  color: 'var(--color-text-primary)', display: 'grid', gap: 2,
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 650 }}>{candidate.label}</span>
                <span style={{ fontSize: 10.5, color: 'var(--color-text-secondary)' }}>{candidate.description ?? candidate.kind}</span>
              </button>
            ))}
          </div>
        )}

        <textarea
          ref={ref}
          value={value}
          onChange={e => { onChange(e.target.value); trackContextQuery(e.target.value) }}
          onKeyDown={handleKey}
          onFocus={() => setComposerFocused(true)}
          onBlur={() => setComposerFocused(false)}
          disabled={disabled}
          aria-label="Message Kitty"
          placeholder="ask kitty anything"
          rows={1}
          style={{
            flex: 1, background: 'none', border: 'none', outline: 'none',
            color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: compact ? 16 : 15,
            resize: 'none', minHeight: 24, maxHeight: 200, lineHeight: 1.5,
            padding: 0,
          }}
        />

        <input
          ref={fileRef}
          type="file"
          multiple
          onChange={onFileChange}
          style={{ display: 'none' }}
        />

        {onOverrideModel && models.length > 0 && (
          <div ref={modelMenuRef} style={{ position: 'relative', flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => setModelMenuOpen((o) => !o)}
              disabled={disabled}
              title="use a different model for the next message"
              aria-label="model override for next message"
              aria-expanded={modelMenuOpen}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: controlSize, height: controlSize,
                background: 'transparent', border: 'none', borderRadius: 99,
                color: overrideModel ? overrideModel.color : 'var(--ink-2)',
                cursor: disabled ? 'not-allowed' : 'pointer',
              }}
            >
              <Zap size={15} />
            </button>
            {modelMenuOpen && (
              <div
                role="menu"
                aria-label="model override menu"
                style={{
                  position: 'absolute', bottom: 44, right: 0, zIndex: 30,
                  minWidth: 160,
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-separator)',
                  borderRadius: 12,
                  padding: 6,
                  boxShadow: 'var(--shadow)',
                  display: 'flex', flexDirection: 'column', gap: 2,
                }}
              >
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9,
                  color: 'var(--ink-2)', padding: '4px 8px 6px',
                  letterSpacing: '0.08em',
                }}>
                  next message only
                </div>
                {models.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onOverrideModel(overrideModel?.id === m.id ? null : m)
                      setModelMenuOpen(false)
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      fontFamily: 'var(--font-mono)', fontSize: 11,
                      textAlign: 'left',
                      color: overrideModel?.id === m.id ? m.color : 'var(--ink)',
                      background: overrideModel?.id === m.id ? 'var(--surface-2)' : 'transparent',
                      border: 'none', borderRadius: 8,
                      padding: '7px 10px', cursor: 'pointer',
                    }}
                  >
                    <span aria-hidden="true" style={{
                      width: 7, height: 7, borderRadius: 99,
                      background: m.color, flexShrink: 0,
                    }} />
                    {m.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={onPickFiles}
          disabled={disabled}
          title="attach a file"
          aria-label="attach a file"
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: controlSize, height: controlSize, flexShrink: 0,
            background: 'transparent',
            border: 'none', borderRadius: 99,
            color: 'var(--ink-2)', cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          <Paperclip size={16} />
        </button>

        {recState !== 'idle' && (
          <button
            onClick={onMicClick}
            disabled={recState === 'transcribing'}
            title={recState === 'recording' ? 'stop recording' : 'transcribing...'}
            aria-label={recState === 'recording' ? 'stop recording' : 'transcribing'}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: controlSize, height: controlSize, flexShrink: 0,
              background: recState === 'recording' ? 'var(--c-red)' : 'transparent',
              border: 'none', borderRadius: 99,
              color: recState === 'recording' ? 'var(--on-primary)' : 'var(--ink-2)',
              cursor: 'pointer',
              animation: recState === 'recording' ? 'blink 1.4s infinite' : 'none',
              opacity: recState === 'transcribing' ? 0.5 : 1,
            }}
          >
            {recState === 'recording' ? <Square size={14} fill="currentColor" /> : <Mic size={16} />}
          </button>
        )}

        {isStreaming ? (
          <button
            onClick={onStop}
            title="stop generating"
            aria-label="stop generating"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: controlSize, height: controlSize, flexShrink: 0,
              background: 'var(--c-red)',
              border: 'none', borderRadius: 99,
              color: '#fff', cursor: 'pointer',
            }}
          >
            <Square size={14} fill="currentColor" />
          </button>
        ) : value.trim() ? (
          <button
            onClick={onSend}
            disabled={disabled}
            aria-label="send message"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: controlSize, height: controlSize, flexShrink: 0,
              background: 'var(--color-accent)',
              border: 'none', borderRadius: 99,
              color: 'var(--on-accent)', cursor: 'pointer',
              boxShadow: 'var(--btn-shadow)',
            }}
          >
            <span style={{ fontSize: 18, fontWeight: 700, lineHeight: 1 }}>↑</span>
          </button>
        ) : !recState.startsWith('rec') ? (
          <button
            onClick={onMicClick}
            title="voice input"
            aria-label="start voice input"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: controlSize, height: controlSize, flexShrink: 0,
              background: 'transparent',
              border: 'none', borderRadius: 99,
              color: 'var(--ink-2)', cursor: 'pointer',
            }}
          >
            <Mic size={16} />
          </button>
        ) : null}
      </div>
    </div>
  )
}
