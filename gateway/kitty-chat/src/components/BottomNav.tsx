'use client'

import { useState } from 'react'

const NAV_ITEMS = [
  { id: 'home', label: 'Home', d: 'M3 11 L12 3 L21 11 M6 9 V20 H18 V9' },
  { id: 'chat', label: 'Chat', d: 'M4 5 H20 V15 H10 L5 19 V15 H4 Z' },
  { id: 'work', label: 'Work', d: 'M5 4 H19 V20 H5 Z M8 8 H10 M14 8 H16 M8 12 H16 M8 16 H12' },
  { id: 'studio', label: 'Image Lab', d: 'M3 4 H21 V20 H3 Z M7 8 L10 4 L13 8 M7 14 L10 10 L13 14' },
  { id: 'library', label: 'Library', d: 'M4 5 H13 V19 H4 Z M17 7 H20 V17 H17 Z M17 5 L14 8' },
  { id: 'more', label: 'More', d: 'M4 7 H20 M4 12 H20 M4 17 H20 M9 5 V9 M15 10 V14 M8 15 V19' },
]

const SECONDARY_ITEMS = [
  { id: 'projects', label: 'Projects' },
  { id: 'agents', label: 'Agents' },
  { id: 'research', label: 'Research' },
  { id: 'automations', label: 'Automations' },
  { id: 'settings', label: 'Settings' },
]
const SECONDARY_IDS = new Set(SECONDARY_ITEMS.map(item => item.id))

interface Props {
  activeView?: string
  onViewChange?: (view: string) => void
}

export function BottomNav({ activeView = 'home', onViewChange }: Props) {
  const [moreOpen, setMoreOpen] = useState(false)

  const selectView = (view: string) => {
    setMoreOpen(false)
    onViewChange?.(view)
  }

  return (
    <>
      {moreOpen && (
        <div role="menu" aria-label="More destinations" style={moreMenuStyle}>
          {SECONDARY_ITEMS.map(item => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              onClick={() => selectView(item.id)}
              style={{ ...moreItemStyle, background: activeView === item.id ? 'var(--color-selected)' : 'transparent', color: activeView === item.id ? 'var(--color-accent)' : 'var(--color-text-primary)' }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      <nav
      aria-label="Main navigation"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: 'var(--bottom-nav-height)',
        background: 'var(--color-surface)',
        borderTop: '1px solid var(--color-separator)',
        display: 'flex',
        justifyContent: 'space-around',
        alignItems: 'center',
        padding: '0 4px env(safe-area-inset-bottom, 0px)',
        zIndex: 50,
      }}
    >
      {NAV_ITEMS.map(({ id, label, d }) => {
        const isMore = id === 'more'
        const active = isMore ? SECONDARY_IDS.has(activeView) : activeView === id
        return (
          <button
            key={id}
            onClick={() => isMore ? setMoreOpen(open => !open) : selectView(id)}
            aria-label={label}
            aria-current={active ? 'page' : undefined}
            aria-haspopup={isMore ? 'menu' : undefined}
            aria-expanded={isMore ? moreOpen : undefined}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              padding: '6px 2px',
              border: 'none',
              cursor: 'pointer',
              color: active ? 'var(--color-accent)' : 'var(--color-text-muted)',
              flex: '1 1 0',
              minWidth: 0,
              minHeight: 44,
              borderRadius: 10,
              background: active ? 'var(--color-selected)' : 'transparent',
            }}
          >
            <svg viewBox="0 0 24 24" style={{ width: 22, height: 22, flexShrink: 0 }}>
              <path d={d} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{
              fontSize: 10,
              fontWeight: 650,
              letterSpacing: '0.02em',
              maxWidth: '100%',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>{label}</span>
          </button>
        )
      })}
      </nav>
    </>
  )
}

const moreMenuStyle: React.CSSProperties = {
  position: 'fixed',
  right: 12,
  bottom: 'calc(var(--bottom-nav-height) + 10px)',
  width: 'min(240px, calc(100vw - 24px))',
  padding: 6,
  display: 'grid',
  gap: 2,
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  boxShadow: '0 10px 30px rgba(15, 23, 42, 0.12)',
  zIndex: 60,
}

const moreItemStyle: React.CSSProperties = {
  minHeight: 48,
  padding: '0 14px',
  border: 'none',
  borderRadius: 'var(--r-control)',
  textAlign: 'left',
  fontFamily: 'var(--font-body)',
  fontSize: 15,
  fontWeight: 650,
  cursor: 'pointer',
}
