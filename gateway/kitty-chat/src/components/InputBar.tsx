'use client'
import { useRef, useEffect, useState, KeyboardEvent, RefObject } from 'react'
import { Mic, Square, Paperclip, X, Zap, AlertCircle, Target, Check, GitBranch } from 'lucide-react'
import { MessageAttachment, Model } from '@/lib/types'
import { useReducedMotion } from '@/hooks/useReducedMotion'

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
  models?: Model[]
  overrideModel?: Model | null
  onOverrideModel?: (m: Model | null) => void
  objective?: string | null
  onObjectiveChange?: (next: string | null) => void
  saveState?: 'idle' | 'saving' | 'saved' | 'failed' | 'offline'
  onRetrySave?: () => void
}

type RecState = 'idle' | 'recording' | 'transcribing'

function formatBytes(n?: number): string {
  if (n === undefined || Number.isNaN(n)) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function ContextWindowProgress({ 
  tokenCount = 0, 
  maxTokens = 200000,
  compact = false 
}: { 
  tokenCount?: number
  maxTokens?: number
  compact?: boolean
}) {
  const prefersReduced = useReducedMotion()
  const percentage = Math.min((tokenCount / maxTokens) * 100, 100)
  const isWarning = percentage >= 80
  const isDanger = percentage >= 95
  const strokeColor = isDanger ? 'var(--c-red)' : isWarning ? 'var(--c-yellow)' : 'var(--cat-green)'
  const strokeWidth = compact ? 3 : 4
  const size = compact ? 28 : 36
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDasharray = circumference
  const strokeDashoffset = circumference * (1 - percentage / 100)

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--surface-2)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          style={{
            transition: prefersReduced ? 'none' : 'stroke-dashoffset 0.5s ease, stroke 0.3s ease',
          }}
        />
      </svg>
      {!compact && (
        <span
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            fontWeight: 600,
            color: strokeColor,
            whiteSpace: 'nowrap',
          }}
        >
          {Math.round(percentage)}%
        </span>
      )}
      {isWarning && !compact && (
        <span
          style={{
            position: 'absolute',
            bottom: -16,
            left: '50%',
            transform: 'translateX(-50%)',
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: strokeColor,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
            whiteSpace: 'nowrap',
          }}
        >
          <AlertCircle size={9} />
          near limit
        </span>
      )}
    </div>
  )
}

export function InputBar({
  value, onChange, onSend, onStop, isStreaming, disabled,
  modelName,
  modelColor,
  textareaRef,
  compact = false,
  attachments = [],
  onAddFiles,
  onRemoveAttachment,
  models = [],
  overrideModel = null,
  onOverrideModel,
  tokenCount = 0,
  maxTokens = 200000,
  objective = null,
  onObjectiveChange,
  saveState = 'idle',
  onRetrySave,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const ref = textareaRef ?? internalRef
  const fileRef = useRef<HTMLInputElement>(null)

  const [recState, setRecState] = useState<RecState>('idle')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const modelMenuRef = useRef<HTMLDivElement>(null)
  const [goalEditing, setGoalEditing] = useState(false)
  const [goalDraft, setGoalDraft] = useState('')

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

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
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

  return (
    <div style={{
      padding: compact ? '12px 12px 16px' : '14px 26px 20px',
      flexShrink: 0,
      background: 'var(--bg)',
    }}>
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

      <div style={{ display: 'flex', gap: 6, marginBottom: 6, paddingLeft: 4, alignItems: 'center', flexWrap: 'wrap' }}>
        {modelName && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: modelColor,
            border: `1.5px solid ${modelColor}`,
            borderRadius: 99, padding: '3px 10px',
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: 99,
              background: modelColor, flexShrink: 0,
            }} />
            {modelName}
          </span>
        )}
        {onObjectiveChange && (
          <span>
            {objective ? (
              <button
                type="button"
                onClick={() => { setGoalDraft(objective); setGoalEditing(true); }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontFamily: 'var(--font-mono)', fontSize: 10,
                  color: 'var(--primary)',
                  border: '1.5px solid var(--primary)',
                  borderRadius: 99, padding: '3px 10px',
                  background: 'transparent', cursor: 'pointer',
                }}
              >
                <Target size={10} />
                <span style={{
                  maxWidth: 160, overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {objective}
                </span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => { setGoalDraft(''); setGoalEditing(true); }}
                title="set a goal for this thread"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  fontFamily: 'var(--font-mono)', fontSize: 10,
                  color: 'var(--ink-2)',
                  border: '1.5px dashed var(--line)',
                  borderRadius: 99, padding: '3px 10px',
                  background: 'transparent', cursor: 'pointer',
                }}
              >
                <Target size={10} />
                goal
              </button>
            )}
          </span>
        )}
        {tokenCount !== undefined && maxTokens !== undefined && (() => {
          const remaining = maxTokens - tokenCount
          const pctUsed = (tokenCount / maxTokens) * 100
          const isWarning = pctUsed > 85
          const isDanger = pctUsed > 95
          const approxMsgs = Math.max(0, Math.floor(remaining / 2000))
          const hint = approxMsgs === 0 ? 'near limit' : `~${approxMsgs} msg${approxMsgs !== 1 ? 's' : ''} left`
          return (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: isDanger ? 'var(--c-red)' : isWarning ? 'var(--c-yellow)' : 'var(--ink-2)',
            }}>
              <span>{(tokenCount / 1000).toFixed(1)}k / {(maxTokens / 1000).toFixed(0)}k</span>
              {(isWarning || isDanger) && (
                <span style={{
                  padding: '1px 5px',
                  borderRadius: 99,
                  background: isDanger ? 'rgba(255,80,80,0.12)' : 'rgba(244,197,66,0.12)',
                }}>
                  {hint}
                </span>
              )}
            </span>
          )
        })()}
      </div>

      {goalEditing && onObjectiveChange && (
        <div style={{
          display: 'flex', gap: 8, marginBottom: 8, paddingLeft: 4, alignItems: 'flex-start',
        }}>
          <textarea
            value={goalDraft}
            onChange={(e) => setGoalDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                onObjectiveChange(goalDraft.trim() || null)
                setGoalEditing(false)
              } else if (e.key === 'Escape') {
                setGoalEditing(false)
              }
            }}
            placeholder="what's this thread for?"
            autoFocus
            rows={2}
            style={{
              flex: 1,
              fontFamily: 'var(--font-body)',
              fontSize: 12,
              lineHeight: 1.5,
              color: 'var(--ink)',
              background: 'var(--surface)',
              border: '1.5px solid var(--primary)',
              borderRadius: 10,
              padding: '6px 10px',
              resize: 'none',
              outline: 'none',
              maxWidth: compact ? '100%' : 480,
            }}
          />
          <div style={{ display: 'flex', gap: 4, paddingTop: 2 }}>
            <button
              type="button"
              onClick={() => {
                onObjectiveChange(goalDraft.trim() || null)
                setGoalEditing(false)
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                fontFamily: 'var(--font-mono)', fontSize: 10,
                color: 'var(--ink)', border: '1.5px solid var(--ink-2)',
                borderRadius: 8, padding: '4px 10px',
                background: 'transparent', cursor: 'pointer',
              }}
            >
              <Check size={12} />
              save
            </button>
            {objective && (
              <button
                type="button"
                onClick={() => { onObjectiveChange(null); setGoalEditing(false); }}
                style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10,
                  color: 'var(--c-red)', border: '1.5px solid var(--c-red)',
                  borderRadius: 8, padding: '4px 10px',
                  background: 'transparent', cursor: 'pointer',
                }}
              >
                clear
              </button>
            )}
            <button
              type="button"
              onClick={() => setGoalEditing(false)}
              style={{
                fontFamily: 'var(--font-mono)', fontSize: 10,
                color: 'var(--ink-2)', border: '1.5px solid var(--line)',
                borderRadius: 8, padding: '4px 10px',
                background: 'transparent', cursor: 'pointer',
              }}
            >
              <X size={12} />
            </button>
          </div>
        </div>
      )}

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        background: 'var(--surface)',
        border: '2.5px solid var(--primary)',
        borderRadius: 18,
        padding: compact ? '12px 14px' : '13px 18px',
        boxShadow: 'var(--input-glow)',
        maxWidth: compact ? '100%' : undefined,
        position: 'relative',
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 15,
          color: 'var(--primary)',
          flexShrink: 0,
        }}>→</span>

        <textarea
          ref={ref}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
          placeholder="ask kitty anything"
          rows={1}
          style={{
            flex: 1, background: 'none', border: 'none', outline: 'none',
            color: 'var(--ink)', fontFamily: 'var(--font-body)', fontSize: 15,
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
                width: 36, height: 36,
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
                  background: 'var(--surface)',
                  border: '1.5px solid var(--line)',
                  borderRadius: 12,
                  padding: 6,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
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

        {/* Context window progress ring */}
        <ContextWindowProgress 
          tokenCount={tokenCount} 
          maxTokens={maxTokens} 
          compact={compact} 
        />

        <button
          type="button"
          onClick={onPickFiles}
          disabled={disabled}
          title="attach a file"
          aria-label="attach a file"
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 36, height: 36, flexShrink: 0,
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
              width: 36, height: 36, flexShrink: 0,
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
              width: 36, height: 36, flexShrink: 0,
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
              width: 36, height: 36, flexShrink: 0,
              background: 'var(--primary)',
              border: 'none', borderRadius: 99,
              color: 'var(--on-primary)', cursor: 'pointer',
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
              width: 36, height: 36, flexShrink: 0,
              background: 'transparent',
              border: 'none', borderRadius: 99,
              color: 'var(--ink-2)', cursor: 'pointer',
            }}
          >
            <Mic size={16} />
          </button>
        ) : null}
      </div>

      {compact && saveState !== 'idle' && (
        <div style={{
          marginTop: 6,
          padding: '0 4px',
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          display: 'flex',
          gap: 6,
          alignItems: 'center',
          color: saveState === 'failed' || saveState === 'offline' ? 'var(--c-red)' : 'var(--ink-2)',
        }}>
          {saveState === 'saving' ? 'saving…' : saveState === 'saved' ? 'saved' : 'save failed'}
          {(saveState === 'failed' || saveState === 'offline') && onRetrySave && (
            <button
              type="button"
              onClick={onRetrySave}
              style={{
                fontFamily: 'var(--font-mono)', fontSize: 9,
                fontWeight: 600, textDecoration: 'underline',
                color: 'inherit', background: 'none', border: 'none',
                cursor: 'pointer', padding: 0,
              }}
            >
              retry
            </button>
          )}
        </div>
      )}
    </div>
  )
}
