'use client'
import { GlyphIcon, type GlyphId } from '@/components/GlyphIcon'

const NAV_ITEMS: { glyph: GlyphId; label: string; view: string }[] = [
  { glyph: 'g-home', label: 'Home', view: 'home' },
  { glyph: 'g-chat', label: 'Chat', view: 'chat' },
  { glyph: 'g-check', label: 'Tasks', view: 'tasks' },
  { glyph: 'g-terminal', label: 'Terminal', view: 'terminal' },
]

interface Props {
  activeView?: string
  onViewChange?: (view: string) => void
  theme?: 'day' | 'night'
  onThemeToggle?: () => void
}

export function Rail({ activeView = 'home', onViewChange, theme = 'day', onThemeToggle }: Props) {
  return (
    <aside style={{
      width: 'var(--rail)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '16px 10px',
      gap: 16,
      borderRight: '1px solid var(--line)',
      background: 'var(--glass)',
      backdropFilter: 'blur(10px)',
      flexShrink: 0,
    }}>
      {/* Cat mark */}
      <div className="cat-mark" aria-label="Kitty">
        <svg viewBox="0 0 28 22" width="28" height="22" fill="none" stroke="var(--cat-outline)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="19" cy="14" rx="7" ry="5" />
          <circle cx="9" cy="11" r="5" />
          <path d="M6 8 L4 3 L10 7" />
          <path d="M11 7 L13 3 L14 8" />
          <circle cx="7" cy="10.5" r=".8" fill="var(--cat-outline)" stroke="none" />
          <path d="M5 13 Q9 16 12.5 13" />
          <path d="M24 14 Q29 12 28 8 Q27.5 6 26 7" />
        </svg>
      </div>

      <nav style={{
        display: 'flex', flexDirection: 'column', gap: 10,
        width: '100%', alignItems: 'center', marginTop: 8,
      }}>
        {NAV_ITEMS.map(({ glyph, label, view }) => {
          const active = activeView === view
          return (
            <button
              key={view}
              aria-label={label}
              onClick={() => onViewChange?.(view)}
              style={{
                width: 44, height: 44,
                borderRadius: 12,
                display: 'grid',
                placeItems: 'center',
                color: active ? 'var(--primary)' : 'var(--ink2)',
                background: active ? 'var(--primary-fade)' : 'transparent',
                border: `1.5px solid ${active ? 'var(--primary)' : 'transparent'}`,
                transition: 'background 0.15s, color 0.15s, border-color 0.15s',
                cursor: 'pointer',
              }}
              onMouseEnter={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.color = 'var(--ink)'
                  el.style.background = 'var(--surface2)'
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.color = 'var(--ink2)'
                  el.style.background = 'transparent'
                }
              }}
            >
              <GlyphIcon id={glyph} size={18} />
            </button>
          )
        })}
      </nav>

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', marginBottom: 8 }}>
        {/* Day/night toggle */}
        <button
          aria-label={theme === 'day' ? 'Switch to night mode' : 'Switch to day mode'}
          onClick={onThemeToggle}
          style={{
            width: 38, height: 38,
            borderRadius: 10,
            display: 'grid',
            placeItems: 'center',
            color: 'var(--ink2)',
            background: 'transparent',
            border: '1.5px solid transparent',
            cursor: 'pointer',
            fontSize: 16,
            transition: 'background 0.15s, color 0.15s',
          }}
          onMouseEnter={e => {
            const el = e.currentTarget as HTMLButtonElement
            el.style.background = 'var(--surface2)'
            el.style.color = 'var(--ink)'
          }}
          onMouseLeave={e => {
            const el = e.currentTarget as HTMLButtonElement
            el.style.background = 'transparent'
            el.style.color = 'var(--ink2)'
          }}
        >
          {theme === 'day' ? '☽' : '☀'}
        </button>

        {/* Settings */}
        <button
          aria-label="Settings"
          onClick={() => onViewChange?.('settings')}
          style={{
            width: 38, height: 38,
            borderRadius: 10,
            display: 'grid',
            placeItems: 'center',
            color: activeView === 'settings' ? 'var(--primary)' : 'var(--ink2)',
            background: activeView === 'settings' ? 'var(--primary-fade)' : 'transparent',
            border: `1.5px solid ${activeView === 'settings' ? 'var(--primary)' : 'transparent'}`,
            transition: 'background 0.15s, color 0.15s',
            cursor: 'pointer',
          }}
          onMouseEnter={e => {
            if (activeView !== 'settings') {
              const el = e.currentTarget as HTMLButtonElement
              el.style.color = 'var(--ink)'
              el.style.background = 'var(--surface2)'
            }
          }}
          onMouseLeave={e => {
            if (activeView !== 'settings') {
              const el = e.currentTarget as HTMLButtonElement
              el.style.color = 'var(--ink2)'
              el.style.background = 'transparent'
            }
          }}
        >
          <GlyphIcon id="g-cog" size={16} />
        </button>

        {/* Online dot */}
        <span style={{
          width: 8, height: 8,
          borderRadius: '50%',
          background: 'var(--c-green)',
          boxShadow: '0 0 8px var(--c-green)',
          display: 'block',
        }} aria-label="Online" />
      </div>
    </aside>
  )
}
