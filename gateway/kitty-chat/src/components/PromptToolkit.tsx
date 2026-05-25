'use client'
import type { CSSProperties } from 'react'

interface PromptTemplate {
  id: string | number
  title: string
  content: string
  category?: string
}

interface Props {
  templates: PromptTemplate[]
  onSelect?: (template: PromptTemplate) => void
  title?: string
}

export function PromptToolkit({ templates, onSelect, title = 'Prompt Toolkit' }: Props) {
  const grouped = templates.reduce((acc, tpl) => {
    const cat = tpl.category || 'General'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(tpl)
    return acc
  }, {} as Record<string, PromptTemplate[]>)

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={headerTitleStyle}>{title}</span>
        <span style={countStyle}>{templates.length} templates</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 4 }}>
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category}>
            <div style={categoryHeaderStyle}>{category}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {items.map(tpl => (
                <div
                  key={tpl.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect?.(tpl)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelect?.(tpl)
                    }
                  }}
                  style={{
                    borderLeft: '2px solid transparent',
                    padding: '9px 14px',
                    cursor: 'pointer',
                    background: 'transparent',
                    transition: 'background 0.15s ease, border-color 0.15s ease',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 8,
                    borderRadius: '0 6px 6px 0',
                  }}
                  onMouseEnter={e => {
                    const el = e.currentTarget as HTMLDivElement
                    el.style.background = 'var(--surface-mid)'
                    el.style.borderLeftColor = 'var(--primary)'
                  }}
                  onMouseLeave={e => {
                    const el = e.currentTarget as HTMLDivElement
                    el.style.background = 'transparent'
                    el.style.borderLeftColor = 'transparent'
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600,
                      color: 'var(--text)', lineHeight: 1.3,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                      {tpl.title}
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--text-dim)',
                      lineHeight: 1.4, marginTop: 2,
                      display: '-webkit-box',
                      WebkitLineClamp: 1,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}>
                      {tpl.content}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {templates.length === 0 && (
          <div style={emptyStyle}>No prompt templates available</div>
        )}
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  paddingTop: 14,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  overflow: 'hidden',
}

const headerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '0 14px 10px',
  borderBottom: '1px solid var(--border-dim)',
}

const headerTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  color: 'var(--text-muted)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
}

const countStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-ghost)',
  letterSpacing: '0.05em',
}

const categoryHeaderStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  color: 'var(--text-ghost)',
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  padding: '8px 14px 4px',
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
  padding: '20px 0',
  fontStyle: 'italic',
}
