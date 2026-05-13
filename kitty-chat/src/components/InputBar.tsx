'use client'
import { useRef, useEffect, KeyboardEvent, RefObject } from 'react'

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

const CHIPS = [
  { key: '/', label: 'Commands' },
  { key: '@', label: 'Context' },
  { key: '⌘K', label: 'History' },
  { key: '+', label: 'Attach' },
]

export function InputBar({
  value, onChange, onSend, disabled,
  chatTitle, modelName, modelColor = 'var(--purple)',
  tokenCount = 0, maxTokens = 200000,
  textareaRef,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const ref = textareaRef ?? internalRef

  // Auto-resize textarea
  useEffect(() => {
    if (!ref.current) return
    ref.current.style.height = 'auto'
    ref.current.style.height = Math.min(ref.current.scrollHeight, 140) + 'px'
  }, [value])

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      onSend()
    }
  }

  const pct = Math.min((tokenCount / maxTokens) * 100, 100)
  const barColor = pct < 50 ? 'var(--mint)' : pct < 80 ? '#f0a500' : 'var(--orange)'
  const countColor = pct < 50 ? 'var(--mint)' : pct < 80 ? '#f0a500' : 'var(--orange)'

  return (
    <div style={{
      flexShrink: 0, padding: '10px 20px 14px',
      background: 'var(--bg)', borderTop: '1px solid var(--border-dim)',
    }}>
      {/* Chips */}
      <div style={{ display: 'flex', gap: 7, marginBottom: 9, flexWrap: 'wrap' }}>
        {CHIPS.map(({ key, label }) => (
          <button
            key={key}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              border: '1px solid #333', borderRadius: 7,
              padding: '6px 14px',
              fontFamily: 'var(--font-ui)', fontSize: 15, fontWeight: 600, letterSpacing: '0.3px',
              color: '#aaa', background: 'var(--bg-card)',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.borderColor = 'var(--purple-glow)'
              el.style.color = 'var(--text)'
              el.style.background = '#1e1a2e'
            }}
            onMouseLeave={e => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.borderColor = '#333'
              el.style.color = '#aaa'
              el.style.background = 'var(--bg-card)'
            }}
          >
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
              color: 'var(--purple-2)', background: 'var(--purple-dim)',
              border: '1px solid color-mix(in srgb, var(--purple) 27%, transparent)',
              borderRadius: 4, padding: '1px 6px',
            }}>{key}</span>
            {label}
          </button>
        ))}
      </div>

      {/* Input box */}
      <div style={{
        border: '1px solid #2a2a2a', borderRadius: 8,
        background: 'var(--bg-raised)', overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}
        onFocusCapture={e => {
          e.currentTarget.style.borderColor = 'var(--purple-glow)'
          e.currentTarget.style.boxShadow = '0 0 20px color-mix(in srgb, var(--purple) 5%, transparent)'
        }}
        onBlurCapture={e => {
          e.currentTarget.style.borderColor = '#2a2a2a'
          e.currentTarget.style.boxShadow = 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <textarea
            ref={ref}
            value={value}
            onChange={e => onChange(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled}
            placeholder="→ ask kitty_"
            rows={2}
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              color: 'var(--text)', fontFamily: 'var(--font-mono)', fontSize: 14,
              padding: '14px 16px', resize: 'none',
              minHeight: 52, maxHeight: 140, lineHeight: 1.6,
            }}
          />
          <button
            onClick={onSend}
            disabled={disabled || !value.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: 7, flexShrink: 0,
              background: 'linear-gradient(135deg, var(--orange), var(--orange-deep))',
              border: 'none', borderRadius: 6, margin: 8,
              color: '#fff', fontFamily: 'var(--font-ui)',
              fontSize: 17, fontWeight: 700, letterSpacing: 1,
              padding: '8px 22px', cursor: disabled ? 'not-allowed' : 'pointer',
              boxShadow: '0 0 14px color-mix(in srgb, var(--orange) 33%, transparent)',
              opacity: disabled || !value.trim() ? 0.5 : 1,
              transition: 'opacity 0.15s, box-shadow 0.15s',
            }}
            onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 22px color-mix(in srgb, var(--orange) 53%, transparent)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 14px color-mix(in srgb, var(--orange) 33%, transparent)' }}
          >
            SEND ↵
          </button>
        </div>
      </div>

      {/* Token progress bar */}
      <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-ghost)', marginBottom: 5 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {chatTitle && (
              <>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: modelColor, boxShadow: `0 0 4px ${modelColor}`, display: 'inline-block' }} />
                {chatTitle}
                {modelName && <span style={{ color: 'var(--text-ghost)' }}> · {modelName}</span>}
              </>
            )}
          </span>
          <span style={{ color: countColor }}>
            {tokenCount > 0 ? `${(tokenCount / 1000).toFixed(1)}k / ${(maxTokens / 1000).toFixed(0)}k tokens` : ''}
          </span>
        </div>
        <div style={{ background: '#1a1a1a', borderRadius: 4, height: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${pct}%`, height: '100%', borderRadius: 4,
            background: `linear-gradient(90deg, ${barColor}, ${barColor})`,
            boxShadow: `0 0 6px color-mix(in srgb, ${barColor} 40%, transparent)`,
            transition: 'width 0.4s ease, background 0.4s ease',
            minWidth: pct > 0 ? 4 : 0,
          }} />
        </div>
      </div>
    </div>
  )
}
