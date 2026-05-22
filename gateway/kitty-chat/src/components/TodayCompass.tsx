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
  onItemSelect 
}: Props) {
  const sortedItems = [...items].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 }
    return order[a.priority] - order[b.priority]
  })

  const cardStyle: CSSProperties = compact 
    ? { ...cardBaseStyle, padding: '10px 14px', minHeight: 70 }
    : cardBaseStyle

  return (
    <div style={containerStyle}>
      {title && (
        <div style={headerStyle}>
          <span style={headerTitleStyle}>{title}</span>
          <span style={countStyle}>{items.length} item{items.length !== 1 ? 's' : ''}</span>
        </div>
      )}
      <div style={gridStyle}>
        {sortedItems.map(item => (
          <div
            key={item.id}
            role="button"
            tabIndex={0}
            onClick={() => {
              item.onSelect?.()
              onItemSelect?.(item)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                item.onSelect?.()
                onItemSelect?.(item)
              }
            }}
            style={{
              ...cardStyle,
              borderLeft: `3px solid ${priorityColor(item.priority)}`,
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLDivElement
              el.style.background = 'var(--surface-mid)'
              el.style.borderColor = priorityColor(item.priority)
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLDivElement
              el.style.background = 'var(--surface-low)'
              el.style.borderColor = 'var(--border)'
            }}
          >
            <div style={cardHeaderStyle}>
              {item.icon && <span style={iconStyle}>{item.icon}</span>}
              <span style={{
                ...priorityBadgeStyle,
                color: priorityColor(item.priority),
                borderColor: priorityColor(item.priority),
              }}>
                {item.priority.toUpperCase()}
              </span>
            </div>
            <div style={itemTitleStyle(item.priority)}>{item.title}</div>
            {item.description && !compact && (
              <div style={descriptionStyle}>{item.description}</div>
            )}
          </div>
        ))}
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
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

const headerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingBottom: 8,
  borderBottom: '1px solid var(--border-dim)',
}

const headerTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--text)',
  marginBottom: 4,
}

const countStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  letterSpacing: '0.05em',
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
  gap: 12,
}

const cardBaseStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '14px 16px',
  transition: 'all 0.2s ease',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

const cardHeaderStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}

const iconStyle: CSSProperties = {
  fontSize: 18,
  lineHeight: 1,
}

const priorityBadgeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  border: '1px solid',
  borderRadius: 4,
  padding: '2px 6px',
  background: 'transparent',
}

const itemTitleStyle = (priority?: PriorityItem['priority']): CSSProperties => ({
  fontFamily: 'var(--font-ui)',
  fontSize: 14,
  fontWeight: 600,
  marginTop: 2,
  color: priority === 'high' ? 'var(--error)' : 'var(--text)',
})

const descriptionStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  color: 'var(--text-dim)',
  lineHeight: 1.5,
  marginTop: 2,
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
  padding: '24px 0',
  fontStyle: 'italic',
}
