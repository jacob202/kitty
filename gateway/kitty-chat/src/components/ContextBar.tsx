'use client'

import { useState, type CSSProperties } from 'react'
import { ChevronDown, ChevronRight, Edit2, Save, RotateCcw } from 'lucide-react'
import { card } from '@/lib/ui'

interface Props {
  tokenCount: number
  maxTokens: number
  expertId?: string | null
  expertLabel?: string
  expertTags?: string[]
  systemPrompt?: string | null
  defaultPrompt?: string | null
  onSavePrompt?: (prompt: string) => void
}

export function ContextBar({ tokenCount, maxTokens, expertId, expertLabel, expertTags, systemPrompt, defaultPrompt, onSavePrompt }: Props) {
  const [promptOpen, setPromptOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const pct = maxTokens > 0 ? Math.min(100, Math.round((tokenCount / maxTokens) * 100)) : 0
  const tone = pct > 80 ? 'var(--c-red)' : pct > 50 ? 'var(--c-yellow)' : 'var(--c-green)'
  const hasExpert = Boolean(expertId && expertLabel)

  const handleEdit = () => {
    setDraft(systemPrompt ?? '')
    setEditing(true)
  }

  const handleSave = () => {
    onSavePrompt?.(draft)
    setEditing(false)
  }

  const handleReset = () => {
    setDraft(defaultPrompt ?? '')
    onSavePrompt?.(defaultPrompt ?? '')
    setEditing(false)
  }

  const handleCancel = () => {
    setDraft('')
    setEditing(false)
  }

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
          {editing ? (
            <div style={{ display: 'grid', gap: 6 }}>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={6}
                style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink)',
                  background: 'var(--surface-2)', border: '1px solid var(--line)',
                  borderRadius: 6, padding: '8px 10px', resize: 'vertical',
                  lineHeight: 1.5, width: '100%',
                }}
              />
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  onClick={handleSave}
                  style={miniBtnStyle}
                >
                  <Save size={10} /> save
                </button>
                {defaultPrompt && (
                  <button
                    type="button"
                    onClick={handleReset}
                    style={{ ...miniBtnStyle, color: 'var(--ink-2)' }}
                  >
                    <RotateCcw size={10} /> reset
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleCancel}
                  style={{ ...miniBtnStyle, color: 'var(--ink-2)', opacity: 0.7 }}
                >
                  cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ position: 'relative' }}>
              <pre style={{
                fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)',
                whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.5,
              }}>
                {systemPrompt}
              </pre>
              <button
                type="button"
                onClick={handleEdit}
                title="Edit prompt"
                style={{
                  position: 'absolute', top: 0, right: 0,
                  ...miniBtnStyle, padding: '2px 6px',
                }}
              >
                <Edit2 size={10} />
              </button>
            </div>
          )}
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

const miniBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600,
  padding: '3px 8px', borderRadius: 4,
  border: '1px solid var(--line)', background: 'var(--surface)',
  color: 'var(--primary)', cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', gap: 4,
}
