'use client'

const NAV_ITEMS: { label: string; short: string; view: string }[] = [
  { label: 'Home', short: 'Ho', view: 'home' },
  { label: 'Chat', short: 'Ch', view: 'chat' },
  { label: 'Tasks', short: 'Tk', view: 'tasks' },
  { label: 'Terminal', short: 'Tr', view: 'terminal' },
]

export function Rail({ activeView = 'home', onViewChange }: { activeView?: string, onViewChange?: (view: string) => void }) {
  return (
    <aside style={{
      width: 'var(--rail)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '16px 10px',
      gap: 16,
      borderRight: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      flexShrink: 0,
    }}>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 14,
        fontWeight: 700,
        color: 'var(--primary)',
        letterSpacing: '0.04em',
        userSelect: 'none',
      }} aria-label="Kitty AI">K</span>

      <nav style={{
        display: 'flex', flexDirection: 'column', gap: 10,
        width: '100%', alignItems: 'center', marginTop: 8,
      }}>
        {NAV_ITEMS.map(({ label, short, view }) => {
          const active = activeView === view
          return (
            <button
              key={view}
              aria-label={label}
              title={label}
              onClick={() => onViewChange?.(view)}
              style={{
                width: 44, height: 44,
                borderRadius: 12,
                display: 'grid',
                placeItems: 'center',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: '0.04em',
                color: active ? 'var(--primary-bright)' : 'var(--text-muted)',
                background: active ? 'var(--surface-mid)' : 'transparent',
                border: `1px solid ${active ? 'var(--border)' : 'transparent'}`,
                boxShadow: active ? 'inset 2px 0 0 var(--primary)' : 'none',
                transition: 'background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease',
                cursor: 'pointer',
              }}
              onMouseEnter={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.color = 'var(--text)'
                  el.style.background = 'var(--surface-low)'
                  el.style.borderColor = 'var(--border-dim)'
                  el.style.transform = 'translateY(-1px)'
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.color = 'var(--text-muted)'
                  el.style.background = 'transparent'
                  el.style.borderColor = 'transparent'
                  el.style.transform = 'none'
                }
              }}
            >
              {short}
            </button>
          )
        })}
      </nav>

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center', marginBottom: 8 }}>
        <button
          aria-label="Settings"
          title="Settings"
          onClick={() => onViewChange?.('settings')}
          style={{
            width: 38, height: 38,
            borderRadius: 10,
            display: 'grid',
            placeItems: 'center',
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: '0.04em',
            color: activeView === 'settings' ? 'var(--primary-bright)' : 'var(--text-muted)',
            background: activeView === 'settings' ? 'var(--surface-mid)' : 'transparent',
            border: `1px solid ${activeView === 'settings' ? 'var(--border)' : 'transparent'}`,
            transition: 'background 0.2s ease, color 0.2s ease, border-color 0.2s ease',
            cursor: 'pointer',
          }}
          onMouseEnter={e => {
            if (activeView !== 'settings') {
              const el = e.currentTarget as HTMLButtonElement
              el.style.color = 'var(--text)'
              el.style.background = 'var(--surface-low)'
              el.style.borderColor = 'var(--border-dim)'
            }
          }}
          onMouseLeave={e => {
            if (activeView !== 'settings') {
              const el = e.currentTarget as HTMLButtonElement
              el.style.color = 'var(--text-muted)'
              el.style.background = 'transparent'
              el.style.borderColor = 'transparent'
            }
          }}
        >
          Set
        </button>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          fontWeight: 700,
          color: 'var(--mint)',
          letterSpacing: '0.06em',
        }} aria-label="Online">on</span>
      </div>
    </aside>
  )
}
