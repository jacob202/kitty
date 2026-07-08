'use client'
import { CatMark } from './CrayonCat'

const NAV_ITEMS: { label: string; view: string; d: string }[] = [
  { label: 'home',      view: 'home',      d: 'M3 11 L12 3 L21 11 M6 9 V20 H18 V9' },
  { label: 'chats',     view: 'chat',      d: 'M4 5 H20 V15 H10 L5 19 V15 H4 Z' },
  { label: 'projects',  view: 'projects',  d: 'M6 4 V20 M6 5 H18 L15 8.5 L18 12 H6' },
  { label: 'docs',      view: 'docs',      d: 'M7 3 H14 L19 8 V21 H7 Z M14 3 V8 H19 M10 12 H16 M10 16 H16' },
  { label: 'providers', view: 'providers', d: 'M9 3 V7 M15 3 V7 M7 7 H17 V11 A5 5 0 0 1 7 11 Z M12 16 V21' },
  { label: 'agents',    view: 'agents',    d: 'M7 8 H17 V17 H7 Z M12 8 V4 M9.5 12 h0.01 M14.5 12 h0.01 M10 14.5 H14' },
  { label: 'image lab', view: 'images',    d: 'M4 5 H20 V19 H4 Z M4 15 L9 10 L13 14 L16 11 L20 15 M15.5 8.5 h0.01' },
  { label: 'settings',  view: 'settings',  d: 'M4 7 H20 M4 12 H20 M4 17 H20 M9 5 V9 M15 10 V14 M8 15 V19' },
]

interface Props {
  activeView?: string
  onViewChange?: (view: string) => void
  theme?: 'day' | 'night'
  onToggleTheme?: () => void
  isMobile?: boolean
}

export function Rail({ activeView = 'home', onViewChange, theme = 'day', onToggleTheme, isMobile }: Props) {
  const themeIconPath = theme === 'night'
    ? 'M12 3 V5 M12 19 V21 M3 12 H5 M19 12 H21 M5.5 5.5 L7 7 M17 17 L18.5 18.5 M18.5 5.5 L17 7 M7 17 L5.5 18.5 M12 8 a4 4 0 1 0 0 8 a4 4 0 0 0 0 -8'
    : 'M19 13 a8 8 0 1 1 -8 -10 a6 6 0 0 0 8 10 Z'

  if (isMobile) {
    return (
      <nav className="safe-bottom" style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'var(--surface-2)',
        borderTop: '1.5px solid var(--line)',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-around',
        paddingTop: 10,
        zIndex: 100,
        boxShadow: '0 -4px 14px rgba(0,0,0,0.05)',
      }}>
        {NAV_ITEMS.map(({ label, view, d }) => {
          const active = activeView === view
          return (
            <button
              key={view}
              onClick={() => onViewChange?.(view)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
                padding: '6px 0',
                border: 'none',
                background: 'transparent',
                color: active ? 'var(--cat-ginger)' : 'var(--ink-2)',
                flex: 1,
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 24, height: 24, marginBottom: 2 }}>
                <path d={d} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#wob)" />
              </svg>
              <span style={{ fontSize: 10, letterSpacing: '0.02em', fontWeight: 600 }}>{label}</span>
            </button>
          )
        })}
      </nav>
    )
  }

  return (
    <nav style={{
      width: 94,
      background: 'var(--surface-2)',
      borderRight: '1.5px solid var(--line)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '18px 0 14px',
      flexShrink: 0,
    }}>
      <div style={{ marginBottom: 22, color: 'var(--cat-ginger)' }}>
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
              style={{
                width: 62,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 5,
                padding: '9px 0',
                border: 'none',
                borderRadius: 14,
                cursor: 'pointer',
                background: active ? 'var(--ginger-fade)' : 'transparent',
                color: active ? 'var(--cat-ginger)' : 'var(--ink-2)',
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 23, height: 23 }}>
                <path d={d} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#wob)" />
              </svg>
              <span style={{ fontSize: 10, letterSpacing: '0.02em', fontWeight: 600 }}>{label}</span>
            </button>
          )
        })}
      </div>

      <button
        onClick={onToggleTheme}
        title="day / night"
        style={{
          width: 46, height: 46, borderRadius: 12,
          border: 'none', background: 'transparent',
          cursor: 'pointer', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          color: 'var(--ink-2)',
        }}
      >
        <svg viewBox="0 0 24 24" style={{ width: 21, height: 21 }}>
          <path d={themeIconPath} stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#wob)" />
        </svg>
      </button>

      <div style={{
        width: 38, height: 38, borderRadius: 99,
        background: 'var(--c-purple)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginTop: 6,
        color: '#fff',
        fontFamily: 'var(--font-display)',
        fontWeight: 800, fontSize: 16,
        boxShadow: 'var(--btn-shadow)',
      }}>
        j
      </div>
    </nav>
  )
}
