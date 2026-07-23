'use client'

const NAV_ITEMS = [
  { id: 'home', label: 'Home', d: 'M3 11 L12 3 L21 11 M6 9 V20 H18 V9' },
  { id: 'chat', label: 'Chat', d: 'M4 5 H20 V15 H10 L5 19 V15 H4 Z' },
  { id: 'work', label: 'Work', d: 'M5 4 H19 V20 H5 Z M8 8 H10 M14 8 H16 M8 12 H16 M8 16 H12' },
  { id: 'studio', label: 'Studio', d: 'M3 4 H21 V20 H3 Z M7 8 L10 4 L13 8 M7 14 L10 10 L13 14' },
  { id: 'builder', label: 'Build', d: 'M5 4 H19 V20 H5 Z M8 8 H16 M8 12 H16 M8 16 H12' },
  { id: 'library', label: 'Library', d: 'M4 5 H13 V19 H4 Z M17 7 H20 V17 H17 Z M17 5 L14 8' },
  { id: 'settings', label: 'More', d: 'M4 7 H20 M4 12 H20 M4 17 H20 M9 5 V9 M15 10 V14 M8 15 V19' },
]

interface Props {
  activeView?: string
  onViewChange?: (view: string) => void
}

export function BottomNav({ activeView = 'home', onViewChange }: Props) {
  return (
    <nav
      aria-label="Main navigation"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: 56,
        background: 'var(--surface-2)',
        borderTop: '1.5px solid var(--line)',
        display: 'flex',
        justifyContent: 'space-around',
        alignItems: 'center',
        padding: '0 4px env(safe-area-inset-bottom)',
        zIndex: 50,
      }}
    >
      {NAV_ITEMS.map(({ id, label, d }) => {
        const active = activeView === id
        return (
          <button
            key={id}
            onClick={() => onViewChange?.(id)}
            aria-label={label}
            aria-current={active ? 'page' : undefined}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              padding: '4px 8px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: active ? 'var(--cat-ginger)' : 'var(--ink-2)',
              minWidth: 44,
              minHeight: 40,
            }}
          >
            <svg viewBox="0 0 24 24" style={{ width: 22, height: 22 }}>
              <path d={d} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.02em' }}>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
