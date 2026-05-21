'use client'
import { useRef, useEffect, useState, KeyboardEvent, RefObject } from 'react'
import { transcribeAudio } from '@/lib/gateway'

type MicState = 'idle' | 'recording' | 'transcribing'

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
  voiceEnabled?: boolean
  onVoiceToggle?: () => void
}

export function InputBar({
  value, onChange, onSend, disabled,
  chatTitle, modelName, modelColor = 'var(--purple)',
  tokenCount = 0, maxTokens = 200000,
  textareaRef,
  voiceEnabled = false,
  onVoiceToggle,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const ref = textareaRef ?? internalRef

  const [micState, setMicState] = useState<MicState>('idle')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    if (!ref.current) return
    ref.current.style.height = 'auto'
    ref.current.style.height = Math.min(ref.current.scrollHeight, 140) + 'px'
  }, [value])

  // Cleanup on unmount
  useEffect(() => () => {
    streamRef.current?.getTracks().forEach(t => t.stop())
  }, [])

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      onSend()
    }
  }

  async function handleMicClick() {
    if (micState === 'recording') {
      mediaRecorderRef.current?.stop()
      return
    }
    if (micState === 'transcribing') return

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []

      recorder.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        setMicState('transcribing')
        try {
          const blob = new Blob(chunksRef.current, { type: mimeType })
          const text = await transcribeAudio(blob)
          if (text) onChange(text)
        } catch (err) {
          console.error('Transcription failed:', err)
        }
        setMicState('idle')
      }

      mediaRecorderRef.current = recorder
      recorder.start(250) // collect chunks every 250ms
      setMicState('recording')
    } catch (err) {
      console.error('Mic access denied:', err)
    }
  }

  const pct = Math.min((tokenCount / maxTokens) * 100, 100)
  const barColor = pct < 50 ? 'var(--mint)' : pct < 80 ? 'var(--yellow)' : 'var(--orange)'

  const micColor = micState === 'recording'
    ? 'var(--orange)'
    : micState === 'transcribing'
    ? 'var(--indigo)'
    : 'var(--text-muted)'

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      padding: '12px 20px 16px',
      background: 'rgba(10, 12, 18, 0.88)',
      backdropFilter: 'blur(14px)',
      borderTop: '1px solid var(--border)',
      zIndex: 10,
    }}>
      <div style={{
        border: '1px solid var(--border)',
        borderRadius: 10,
        background: 'var(--recessed)',
        overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}
        onFocusCapture={e => {
          e.currentTarget.style.borderColor = 'var(--border-soft)'
          e.currentTarget.style.boxShadow = '0 0 20px rgba(102, 119, 204, 0.08)'
        }}
        onBlurCapture={e => {
          e.currentTarget.style.borderColor = 'var(--border)'
          e.currentTarget.style.boxShadow = 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          {/* Mic button */}
          <button
            onClick={() => void handleMicClick()}
            disabled={disabled}
            title={micState === 'recording' ? 'stop recording' : 'speak'}
            style={{
              flexShrink: 0,
              background: 'transparent',
              border: 'none',
              padding: '10px 8px 10px 14px',
              cursor: disabled ? 'not-allowed' : 'pointer',
              color: micColor,
              fontSize: 18,
              lineHeight: 1,
              opacity: disabled ? 0.3 : 1,
              transition: 'color 0.2s',
            }}
          >
            {micState === 'transcribing' ? '◌' : micState === 'recording' ? '⏹' : '🎙'}
          </button>

          <textarea
            ref={ref}
            value={value}
            onChange={e => onChange(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled}
            placeholder={micState === 'transcribing' ? 'transcribing…' : '→ ask kitty_'}
            rows={2}
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              color: 'var(--text)', fontFamily: 'var(--font-mono)', fontSize: 14,
              padding: '12px 8px', resize: 'none',
              minHeight: 48, maxHeight: 140, lineHeight: 1.6,
            }}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0 8px 8px' }}>
            {/* TTS toggle */}
            {onVoiceToggle && (
              <button
                onClick={onVoiceToggle}
                title={voiceEnabled ? 'voice on — click to mute' : 'voice off — click to enable'}
                style={{
                  background: voiceEnabled ? 'rgba(33, 189, 217, 0.15)' : 'transparent',
                  border: '1px solid ' + (voiceEnabled ? 'rgba(33,189,217,0.3)' : 'var(--border-dim)'),
                  borderRadius: 6,
                  color: voiceEnabled ? 'var(--teal)' : 'var(--text-faint)',
                  fontSize: 15,
                  padding: '5px 8px',
                  cursor: 'pointer',
                  lineHeight: 1,
                  transition: 'all 0.15s',
                }}
              >
                {voiceEnabled ? '🔊' : '🔇'}
              </button>
            )}

            {/* Send button */}
            <button
              onClick={onSend}
              disabled={disabled || !value.trim()}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0,
                background: 'var(--teal)',
                border: 'none', borderRadius: 7,
                color: '#0a1210', fontFamily: 'var(--font-ui)',
                fontSize: 18, letterSpacing: 0.5,
                padding: '7px 18px', cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
                opacity: disabled || !value.trim() ? 0.4 : 1,
                transition: 'opacity 0.15s, background 0.15s',
              }}
              onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = 'var(--orange)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--teal)' }}
            >
              send ↵
            </button>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 7, fontFamily: 'var(--font-mono)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-ghost)', marginBottom: 4 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {chatTitle && (
              <>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: modelColor, display: 'inline-block' }} />
                {chatTitle}
                {modelName && <span style={{ color: 'var(--text-ghost)' }}> · {modelName}</span>}
              </>
            )}
            {micState === 'recording' && (
              <span style={{ color: 'var(--orange)', animation: 'pulse 1s infinite' }}>● recording</span>
            )}
          </span>
          <span style={{ color: barColor }}>
            {tokenCount > 0 ? `${(tokenCount / 1000).toFixed(1)}k / ${(maxTokens / 1000).toFixed(0)}k` : '⌘↵ to send'}
          </span>
        </div>
        <div style={{ background: 'var(--border-dim)', borderRadius: 4, height: 2, overflow: 'hidden' }}>
          <div style={{
            width: `${pct}%`, height: '100%', borderRadius: 4,
            background: barColor,
            transition: 'width 0.4s ease, background 0.4s ease',
            minWidth: pct > 0 ? 4 : 0,
          }} />
        </div>
      </div>
    </div>
  )
}
