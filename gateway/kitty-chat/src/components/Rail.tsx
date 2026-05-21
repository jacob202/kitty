'use client'

export function Rail() {
  return (
    <nav style={{
      width: 'var(--rail)',
      height: '100vh',
      borderRight: '1px solid var(--border)',
      background: 'var(--bg-deep)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      paddingTop: 16,
      gap: 4,
      flexShrink: 0,
    }}>
      <div
        className="pixel-kitty"
        style={{ width: 36, height: 36, borderRadius: 8, marginBottom: 8 }}
        aria-label="Kitty"
      />
    </nav>
  )
}
