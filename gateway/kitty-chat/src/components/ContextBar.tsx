'use client'

import { useState, type CSSProperties } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { card, bodyText } from '@/lib/ui'

interface Props {
  tokenCount: number
  maxTokens: number
  expertId?: string | null
  expertLabel?: string
  expertTags?: string[]
  systemPrompt?: string | null
}

export function ContextBar({ tokenCount, maxTokens, expertId, expertLabel, expertTags, systemPrompt }: Props) {
  const [promptOpen, setPromptOpen] = useState(false)
  const pct = maxTokens > 0 ? Math.min(100, Math.round((tokenCount / maxTokens) * 100)) : 0
  const tone = pct > 80 ? 'var(--c-red)' : pct > 50 ? 'var(--c-yellow)' : 'var(--c-green)'
  const hasExpert = Boolean(expertId && expertLabel)

  if (tokenCount === 0 && !hasExpert) return null

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 6,
      padding: '6px 24px',
      borderBottom: '1.5px solid var(--line)',
      background: 'var(--surface-2)',
    }}>
      {hasExpert && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setPromptOpen(!promptOpen)}
            style={{
              ...expertButtonStyle,
              display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, color: 'var(--primary)' }}>
              {expertLabel}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
              expert
            </span>
            {promptOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </button>
          {expertTags && expertTags.length > 0 && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', opacity: 0.7 }}>
              {expertTags.slice(0, 3).join(', ')}
            </span>
          )}
        </div>
      )}

      {promptOpen && systemPrompt && (
        <div style={{ ...card, padding: '8px 12px', maxWidth: 760, marginBottom: 4 }}>
          <pre style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)',
            whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.5,
          }}>
            {systemPrompt}
          </pre>
        </div>
      )}

      {tokenCount > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            flex: 1, height: 3, borderRadius: 99,
            background: 'var(--surface)', overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', width: `${Math.max(1, pct)}%`,
              background: tone, borderRadius: 99,
              transition: 'width 0.3s ease',
            }} />
          </div>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: tone,
            whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            {(tokenCount / 1000).toFixed(1)}k / {(maxTokens / 1000).toFixed(0)}k tokens
          </span>
        </div>
      )}
    </div>
  )
}

const expertButtonStyle: CSSProperties = {
  background: 'rgba(102,119,204,0.08)',
  border: '1px solid rgba(102,119,204,0.2)',
  borderRadius: 6,
  padding: '3px 10px',
  cursor: 'pointer',
  color: 'var(--ink)',
}
