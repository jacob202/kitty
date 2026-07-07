'use client'
import type { CSSProperties } from 'react'
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState, sectionLabel } from '@/lib/ui'
import { Skeleton } from './Skeleton'

interface PromptTemplate {
  id: string | number
  title: string
  content: string
  category?: string
  icon?: string
}

interface Props {
  templates: PromptTemplate[]
  onSelect?: (template: PromptTemplate) => void
  title?: string
  isLoading?: boolean
}

export function PromptToolkit({ templates, onSelect, title = 'Prompt Toolkit', isLoading = false }: Props) {
  const grouped = templates.reduce((acc, tpl) => {
    const cat = tpl.category || 'General'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(tpl)
    return acc
  }, {} as Record<string, PromptTemplate[]>)

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>{title}</span>
        <span style={countStyle}>{templates.length} templates</span>
      </div>
      <div style={bodyStyle}>
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category} style={categoryGroupStyle}>
            <div style={categoryHeaderStyle}>{category}</div>
            <div style={templateListStyle}>
              {items.map(tpl => (
                <div
                  key={tpl.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect?.(tpl)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelect?.(tpl)
                    }
                  }}
                  style={templateCardStyle}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget as HTMLDivElement
                    el.style.background = 'var(--surface)'
                    el.style.borderColor = 'var(--primary)'
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget as HTMLDivElement
                    el.style.background = 'var(--bg)'
                    el.style.borderColor = 'var(--line)'
                  }}
                >
                  <div style={templateHeaderStyle}>
                    {tpl.icon && <span style={iconStyle}>{tpl.icon}</span>}
                    <span style={templateTitleStyle}>{tpl.title}</span>
                  </div>
                  <div style={templatePreviewStyle}>
                    {tpl.content.slice(0, 100)}
                    {tpl.content.length > 100 ? '...' : ''}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {templates.length === 0 && (
          isLoading ? (
            <div style={{ display: 'grid', gap: 8 }}>
              <Skeleton height={64} />
              <Skeleton height={64} />
            </div>
          ) : (
            <div style={emptyStyle}>no prompt templates yet</div>
          )
        )}
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = { ...card, display: 'flex', flexDirection: 'column', gap: 12 }
const headerStyle: CSSProperties = cardHeader
const titleStyle: CSSProperties = cardTitle
const countStyle: CSSProperties = cardMeta

const bodyStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 16,
}

const categoryGroupStyle: CSSProperties = {}

const categoryHeaderStyle: CSSProperties = { ...sectionLabel, marginBottom: 8, marginTop: 4 }

const templateListStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
  gap: 8,
}

const templateCardStyle: CSSProperties = { ...itemCard, padding: '12px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 6 }

const templateHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
}

const iconStyle: CSSProperties = {
  fontSize: 16,
  lineHeight: 1,
}

const templateTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--ink)',
}

const templatePreviewStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  color: 'var(--ink-2)',
  lineHeight: 1.4,
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
}

const emptyStyle: CSSProperties = emptyState
