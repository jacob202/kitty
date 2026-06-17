'use client'
import { useRef, useEffect, useState, KeyboardEvent, RefObject } from 'react'
import { Mic, Square } from 'lucide-react'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled?: boolean
  chatTitle?: string
  modelName?: string
  modelColor?: string
  tokenCount?: number
  maxTokens?: number
  textareaRef?: RefObject<HTMLTextAreaElement | null>
}

type RecState = 'idle' | 'recording' | 'transcribing'

export function InputBar({
  value, onChange, onSend, disabled,
  chatTitle, modelName, modelColor = 'var(--purple)',
  tokenCount = 0, maxTokens = 200000,
  textareaRef,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const ref = textareaRef ?? internalRef

  const [recState, setRecState] = useState<RecState>('idle')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  // Mirror the latest value into a ref so transcribeAndInsert, which runs
  // asynchronously after recording stops, doesn't overwrite anything the
  // user typed during transcription.
  const valueRef = useRef<string>(value)
  useEffect(() => { valueRef.current = value }, [value])

  useEffect(() => {
    if (!ref.current) return
    ref.current.style.height = 'auto'
    ref.current.style.height = Math.min(ref.current.scrollHeight, 200) + 'px'
  }, [value])

  // Stop the mic stream if the input unmounts mid-recording.
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
      // eslint-disable-next-line no-console
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
      // No model field: gateway/stt.py uses faster-whisper with its own
      // configured size and ignores the OpenAI-style 'model' form value.
      const res = await fetch('/proxy/v1/audio/transcriptions', { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Transcription HTTP ${res.status}`)
      const json = await res.json()
      const text = (json?.text ?? '').trim()
      if (text) {
        const currentValue = valueRef.current
        onChange(currentValue ? `${currentValue.trim()} ${text}` : text)
        ref.current?.focus()
      }
    } catch (err) {
      // eslint-disable-next-line no-console
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
      if (e.shiftKey) return // allow Shift+Enter for new line
      e.preventDefault()
      if (!disabled && value.trim()) onSend()
    }
  }

  const pct = Math.min((tokenCount / maxTokens) * 100, 100)
  const barColor = pct < 50 ? 'var(--mint)' : pct < 80 ? 'var(--yellow)' : 'var(--error)'
  const countColor = pct < 80 ? 'var(--text-ghost)' : 'var(--warning)'

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      padding: '16px 24px 20px',
      background: 'linear-gradient(to top, var(--bg) 60%, transparent)',
      pointerEvents: 'none',
      zIndex: 10,
    }}>
      <div style={{ pointerEvents: 'auto', maxWidth: 840, margin: '0 auto' }}>
        <div style={{
          border: '1px solid var(--border)',
          borderRadius: 16,
          background: 'var(--surface-mid)',
          overflow: 'hidden',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
          transition: 'border-color 0.2s, box-shadow 0.2s',
          display: 'flex',
          flexDirection: 'column',
        }}
          onFocusCapture={e => {
            e.currentTarget.style.borderColor = 'var(--primary)'
            e.currentTarget.style.boxShadow = '0 8px 32px rgba(232, 120, 69, 0.12)'
          }}
          onBlurCapture={e => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.4)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px' }}>
            <textarea
              ref={ref}
              value={value}
              onChange={e => onChange(e.target.value)}
              onKeyDown={handleKey}
              disabled={disabled}
              placeholder="Ask kitty anything..."
              rows={1}
              style={{
                flex: 1, background: 'none', border: 'none', outline: 'none',
                color: 'var(--text)', fontFamily: 'var(--font-ui)', fontSize: 15,
                padding: '14px 16px', resize: 'none',
                minHeight: 48, maxHeight: 200, lineHeight: 1.5,
              }}
            />
            <button
              onClick={onMicClick}
              disabled={recState === 'transcribing'}
              title={recState === 'recording' ? 'Stop recording' : recState === 'transcribing' ? 'Transcribing…' : 'Voice input'}
              aria-label={recState === 'recording' ? 'Stop recording' : 'Start voice input'}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 36, height: 36, flexShrink: 0,
                background: recState === 'recording' ? 'var(--error)' : 'transparent',
                border: 'none', borderRadius: 10, margin: '6px 4px 6px 0',
                color: recState === 'recording' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'background 0.15s ease, color 0.15s ease',
                animation: recState === 'recording' ? 'blink 1.4s infinite' : 'none',
                opacity: recState === 'transcribing' ? 0.5 : 1,
              }}
            >
              {recState === 'recording' ? <Square size={16} fill="currentColor" /> : <Mic size={18} />}
            </button>
            <button
              onClick={onSend}
              disabled={disabled || !value.trim()}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 36, height: 36, flexShrink: 0,
                background: value.trim() ? 'var(--primary)' : 'var(--surface-high)',
                border: 'none', borderRadius: 10, margin: '6px 8px 6px 0',
                color: value.trim() ? '#fff' : 'var(--text-muted)',
                cursor: disabled ? 'default' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={e => { if (!disabled && value.trim()) (e.currentTarget as HTMLButtonElement).style.background = 'var(--orange-deep)' }}
              onMouseLeave={e => { if (!disabled && value.trim()) (e.currentTarget as HTMLButtonElement).style.background = 'var(--primary)' }}
              aria-label="Send message"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="19" x2="12" y2="5"></line>
                <polyline points="5 12 12 5 19 12"></polyline>
              </svg>
            </button>
          </div>
        </div>

        <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-ghost)', marginBottom: 4, padding: '0 4px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {chatTitle && (
                <>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: modelColor, display: 'inline-block' }} />
                  {chatTitle}
                  {modelName && <span style={{ color: 'var(--text-ghost)' }}> · {modelName}</span>}
                </>
              )}
            </span>
            <span style={{ color: countColor }}>
              {tokenCount > 0 ? `${(tokenCount / 1000).toFixed(1)}k / ${(maxTokens / 1000).toFixed(0)}k` : 'Enter to send'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
