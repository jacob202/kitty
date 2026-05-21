'use client'

const NAV_ITEMS = [
  { icon: '⌂', label: 'Home' },
  { icon: '☰', label: 'Chat' },
  { icon: '✓', label: 'Tasks' },
  { icon: '□', label: 'Files' },
  { icon: '✎', label: 'Notes' },
  { icon: '⚡', label: 'Tools' },
]

export function Rail({ activeView = 'home' }: { activeView?: string }) {
  return (
    <aside style={{
      width: 'var(--rail)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '14px 10px',
      gap: 16,
      borderRight: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      flexShrink: 0,
    }}>
      <div className="pixel-kitty" aria-label="Kitty AI" />

      <nav style={{
        display: 'flex', flexDirection: 'column', gap: 8,
        width: '100%', alignItems: 'center', marginTop: 4,
      }}>
        {NAV_ITEMS.map(({ icon, label }, i) => {
          const active = (i === 0 && activeView === 'home') || (i === 1 && activeView === 'chat')
          return (
            <button
              key={label}
              aria-label={label}
              style={{
                width: 42, height: 42,
                borderRadius: 14,
                display: 'grid',
                placeItems: 'center',
                fontSize: 18,
                color: active ? 'var(--orange)' : 'var(--text-muted)',
                background: active ? 'rgba(232, 120, 69, 0.1)' : 'transparent',
                border: `1px solid ${active ? 'rgba(232, 120, 69, 0.24)' : 'transparent'}`,
                transition: 'background 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease',
                cursor: 'pointer',
              }}
              onMouseEnter={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.color = 'var(--text)'
                  el.style.background = 'var(--panel-2)'
                  el.style.borderColor = 'var(--border)'
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

      <div style={{ marginTop: 'auto' }}>
        <span style={{
          width: 10, height: 10,
          borderRadius: '50%',
          background: 'var(--mint)',
          boxShadow: '0 0 18px rgba(115, 217, 159, 0.55)',
          display: 'block',
        }} aria-label="Online" />
      </div>
    </aside>
  )
}
