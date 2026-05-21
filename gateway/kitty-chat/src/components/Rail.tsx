'use client'

const NAV_ITEMS = [
  { icon: '⌂', label: 'Home', view: 'home' },
  { icon: '☰', label: 'Chat', view: 'chat' },
  { icon: '✓', label: 'Tasks', view: 'tasks' },
  { icon: '□', label: 'Files', view: 'files' },
  { icon: '✎', label: 'Notes', view: 'notes' },
  { icon: '⚡', label: 'Tools', view: 'tools' },
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
      <div className="pixel-kitty" aria-label="Kitty AI" />

      <nav style={{
        display: 'flex', flexDirection: 'column', gap: 10,
        width: '100%', alignItems: 'center', marginTop: 8,
      }}>
        {NAV_ITEMS.map(({ icon, label, view }) => {
          const active = activeView === view
          return (
            <button
              key={label}
              aria-label={label}
              onClick={() => onViewChange?.(view)}
              style={{
                width: 44, height: 44,
                borderRadius: 12,
                display: 'grid',
                placeItems: 'center',
                fontSize: 18,
                color: active ? 'var(--primary-bright)' : 'var(--text-muted)',
                background: active ? 'var(--surface-mid)' : 'transparent',
                border: `1px solid ${active ? 'var(--border)' : 'transparent'}`,
                transition: 'background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.2s ease',
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
              {icon}
            </button>
          )
        })}
      </nav>

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center', marginBottom: 8 }}>
        <button
          aria-label="Settings"
          onClick={() => onViewChange?.('settings')}
          style={{
            width: 38, height: 38,
            borderRadius: 10,
            display: 'grid',
            placeItems: 'center',
            fontSize: 16,
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
        >⚙</button>
        <span style={{
          width: 8, height: 8,
          borderRadius: '50%',
          background: 'var(--mint)',
          boxShadow: '0 0 12px rgba(115, 217, 159, 0.4)',
          display: 'block',
        }} aria-label="Online" />
      </div>
    </aside>
  )
}
