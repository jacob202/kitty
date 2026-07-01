'use client'
import { useRef, useEffect, useState, KeyboardEvent, RefObject } from 'react'
import { Mic, Square } from 'lucide-react'

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
}

type RecState = 'idle' | 'recording' | 'transcribing'

export function InputBar({
  value, onChange, onSend, onStop, isStreaming, disabled,
  textareaRef,
  compact = false,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const ref = textareaRef ?? internalRef

  const [recState, setRecState] = useState<RecState>('idle')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

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

  return (
    <div style={{
      padding: '14px 26px 20px',
      flexShrink: 0,
      background: 'var(--bg)',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        background: 'var(--surface)',
        border: '2px solid var(--primary)',
        borderRadius: 16,
        padding: '12px 16px',
        boxShadow: 'var(--input-glow)',
        maxWidth: compact ? '100%' : undefined,
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
    </div>
  )
}
