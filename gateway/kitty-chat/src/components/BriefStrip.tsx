'use client'

interface Props {
  intention: string | null
  weather?: string | null
  overdueCount?: number
  focusText?: string | null
}

interface BriefCard {
  label: string
  value: string
  sub: string
  accent: string
  dim: boolean
}

export function BriefStrip({
  intention,
  weather = null,
  overdueCount = 0,
  focusText = null,
}: Props) {
  const cards: BriefCard[] = [
    {
      label: 'WEATHER',
      value: weather?.trim() || '—',
      sub: weather ? 'live' : 'no data',
      accent: 'var(--blue)',
      dim: !weather,
    },
    {
      label: 'NEXT UP',
      value: intention?.trim() || '—',
      sub: intention ? 'from brief' : 'waiting on gateway',
      accent: 'var(--primary)',
      dim: !intention,
    },
    {
      label: 'OVERDUE',
      value: overdueCount > 0 ? String(overdueCount) : '—',
      sub: overdueCount > 0 ? `act now` : 'nothing flagged',
      accent: overdueCount > 0 ? 'var(--error)' : 'var(--border)',
      dim: overdueCount === 0,
    },
    {
      label: 'FOCUS',
      value: focusText?.trim() || '—',
      sub: focusText ? 'active todo' : 'see compass',
      accent: 'var(--mint)',
      dim: !focusText,
    },
  ]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 8,
    }}>
      {cards.map(card => (
        <div key={card.label} style={{
          position: 'relative',
          background: 'var(--surface-low)',
          border: '1px solid var(--border)',
          borderLeft: `2px solid ${card.dim ? 'var(--border)' : card.accent}`,
          borderRadius: '0 8px 8px 0',
          padding: '12px 14px 10px',
          overflow: 'hidden',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '1.6px',
            color: 'var(--text-ghost)',
            fontWeight: 700,
            marginBottom: 6,
            textTransform: 'uppercase' as const,
          }}>
            {card.label}
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 15,
            fontWeight: 700,
            color: card.dim ? 'var(--text-muted)' : card.accent,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: 1.2,
          }}>
            {card.value}
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--text-ghost)',
            marginTop: 4,
          }}>
            {card.sub}
          </div>
        </div>
      ))}
    </div>
  )
}
