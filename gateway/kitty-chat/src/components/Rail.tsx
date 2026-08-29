'use client'
import { CatMark } from './CrayonCat'

const NAV_ITEMS: { label: string; view: string; d: string }[] = [
  { label: 'Home',      view: 'home',      d: 'M3 11 L12 3 L21 11 M6 9 V20 H18 V9' },
  { label: 'Chat',      view: 'chat',      d: 'M4 5 H20 V15 H10 L5 19 V15 H4 Z' },
  { label: 'Work',      view: 'work',      d: 'M5 4 H19 V20 H5 Z M8 8 H10 M14 8 H16 M8 12 H16 M8 16 H12' },
  { label: 'Projects',  view: 'projects',  d: 'M3 7 H9 L11 9 H21 V19 H3 Z' },
  { label: 'Image Lab',    view: 'studio',    d: 'M3 4 H21 V20 H3 Z M7 8 L10 4 L13 8 M7 14 L10 10 L13 14' },
  { label: 'Library',   view: 'library',   d: 'M4 5 H13 V19 H4 Z M17 7 H20 V17 H17 Z M17 5 L14 8' },
  { label: 'Automations', view: 'automations', d: 'M12 3 A9 9 0 1 1 3 12 A9 9 0 0 1 12 3 M12 7 V12 L15 14' },
  { label: 'Settings',  view: 'settings',  d: 'M4 7 H20 M4 12 H20 M4 17 H20 M9 5 V9 M15 10 V14 M8 15 V19' },
]

interface Props {
  activeView?: string
  onViewChange?: (view: string) => void
  theme?: 'cosmic' | 'day' | 'night'
  onToggleTheme?: () => void
}

export function Rail({ activeView = 'home', onViewChange, theme = 'cosmic', onToggleTheme }: Props) {
  const themeIconPath = theme === 'night'
    ? 'M12 3 V5 M12 19 V21 M3 12 H5 M19 12 H21 M5.5 5.5 L7 7 M17 17 L18.5 18.5 M18.5 5.5 L17 7 M7 17 L5.5 18.5 M12 8 a4 4 0 1 0 0 8 a4 4 0 0 0 0 -8'
    : theme === 'cosmic'
    ? 'M12 2 L13.5 10 L22 12 L13.5 14 L12 22 L10.5 14 L2 12 L10.5 10 Z'
    : 'M19 13 a8 8 0 1 1 -8 -10 a6 6 0 0 0 8 10 Z'

  return (
    <nav aria-label="Primary navigation" style={{
      width: 'var(--rail-width)',
      background: 'var(--color-surface)',
      borderRight: '1px solid var(--color-separator)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '16px 8px 14px',
      flexShrink: 0,
    }}>
      <div style={{ marginBottom: 20, color: 'var(--color-accent)' }}>
        <CatMark />
      </div>

      <div style={{
        display: 'flex', flexDirection: 'column', gap: 4,
        width: '100%', alignItems: 'center', flex: 1,
      }}>
        {NAV_ITEMS.map(({ label, view, d }) => {
          const active = activeView === view
          return (
            <button
              key={view}
              onClick={() => onViewChange?.(view)}
              aria-label={label}
              aria-current={active ? 'page' : undefined}
              style={{
                width: 64,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 5,
                padding: '8px 4px', minHeight: 52,
                border: 'none',
                borderRadius: 12,
                cursor: 'pointer',
                background: active ? 'var(--color-selected)' : 'transparent',
                color: active ? 'var(--color-accent)' : 'var(--color-text-muted)',
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 23, height: 23 }}>
                <path d={d} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span style={{ fontSize: 11, letterSpacing: '-0.01em', fontWeight: 650 }}>{label}</span>
            </button>
          )
        })}
      </div>

      <button
        onClick={onToggleTheme}
        aria-label="Switch appearance"
        title={theme === 'cosmic' ? 'theme: cosmic — switch to day' : theme === 'day' ? 'theme: day — switch to night' : 'theme: night — switch to cosmic'}
        style={{
          width: 46, height: 46, borderRadius: 12,
          border: 'none', background: 'transparent',
          cursor: 'pointer', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          color: 'var(--color-text-muted)',
        }}
      >
        <svg viewBox="0 0 24 24" style={{ width: 21, height: 21 }}>
          <path d={themeIconPath} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <div style={{
        width: 38, height: 38, borderRadius: 99,
        background: 'var(--color-surface-elevated)', border: '1px solid var(--color-separator)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginTop: 6,
        color: 'var(--color-text-primary)',
        fontFamily: 'var(--font-display)',
        fontWeight: 800, fontSize: 16,
        boxShadow: 'none',
      }}>
        j
      </div>
    </nav>
  )
}
