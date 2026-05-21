'use client'

interface Props {
  sessionCount?: number
}

export function Rail({ sessionCount }: Props) {
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
      {sessionCount != null && sessionCount > 0 && (
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--text-muted)',
          lineHeight: 1,
        }}>
          {sessionCount}
        </span>
      )}
    </nav>
  )
}
