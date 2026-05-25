'use client'
import type { CSSProperties } from 'react'

export interface PriorityItem {
  id: string | number
  title: string
  description?: string
  priority: 'high' | 'medium' | 'low'
  icon?: string
  onSelect?: () => void
}

interface Props {
  items: PriorityItem[]
  title?: string
  compact?: boolean
  onItemSelect?: (item: PriorityItem) => void
}

function priorityColor(priority: PriorityItem['priority']): string {
  switch (priority) {
    case 'high':   return 'var(--error)'
    case 'medium': return 'var(--orange)'
    case 'low':    return 'var(--mint)'
  }
}

export function TodayCompass({
  items,
  title = "Today's Compass",
  compact = false,
  onItemSelect,
}: Props) {
  const sortedItems = [...items].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 }
    return order[a.priority] - order[b.priority]
  })

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={headerTitleStyle}>{title}</span>
        <span style={countStyle}>{items.length} item{items.length !== 1 ? 's' : ''}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {sortedItems.map(item => {
          const pColor = priorityColor(item.priority)
          return (
            <div
              key={item.id}
              role="button"
              tabIndex={0}
              onClick={() => { item.onSelect?.(); onItemSelect?.(item) }}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  item.onSelect?.()
                  onItemSelect?.(item)
                }
              }}
              style={{
                borderLeft: `2px solid ${pColor}`,
                padding: compact ? '8px 12px' : '10px 14px',
                cursor: 'pointer',
                background: 'transparent',
                transition: 'background 0.15s ease',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                borderRadius: '0 6px 6px 0',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--surface-mid)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
            >
              {item.icon && <span style={{ fontSize: 14, marginTop: 1, flexShrink: 0 }}>{item.icon}</span>}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                    letterSpacing: '0.1em', textTransform: 'uppercase' as const,
                    color: pColor, border: `1px solid ${pColor}`,
                    borderRadius: 3, padding: '1px 5px',
                  }}>
                    {item.priority}
                  </span>
                </div>
                <div style={{
                  fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600,
                  color: 'var(--text)', lineHeight: 1.3,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {item.title}
                </div>
                {item.description && !compact && (
                  <div style={{
                    fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--text-dim)',
                    lineHeight: 1.4, marginTop: 2,
                  }}>
                    {item.description}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {items.length === 0 && (
        <div style={emptyStyle}>No priority items for today</div>
      )}
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  paddingTop: 14,
  paddingBottom: 8,
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

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
  padding: '20px 0',
  fontStyle: 'italic',
}
