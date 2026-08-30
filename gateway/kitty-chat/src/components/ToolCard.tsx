'use client'

interface ToolCardProps {
  title: string
  children: React.ReactNode
}

export function ToolCard({ title, children }: ToolCardProps) {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1.5px solid var(--line)',
        borderRadius: 12,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'lowercase',
          color: 'var(--ink-2)',
          paddingBottom: 8,
          borderBottom: '1px solid var(--line)',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  )
}
