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
  color: 'default' | 'orange' | 'red' | 'teal'
}

function cardColor(color: BriefCard['color']): string {
  if (color === 'orange') return 'var(--orange)'
  if (color === 'red')    return '#e74c3c'
  if (color === 'teal')   return 'var(--teal)'
  return 'var(--text)'
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
      color: 'default',
    },
    {
      label: 'NEXT UP',
      value: intention?.trim() || '—',
      sub: intention ? 'from brief' : 'waiting on gateway',
      color: 'orange',
    },
    {
      label: 'OVERDUE',
      value: overdueCount > 0 ? String(overdueCount) : '—',
      sub: overdueCount > 0 ? `${overdueCount} open todo${overdueCount === 1 ? '' : 's'}` : 'nothing flagged',
      color: overdueCount > 0 ? 'red' : 'default',
    },
    {
      label: 'FOCUS',
      value: focusText?.trim() || '—',
      sub: focusText ? 'active todo' : 'see compass',
      color: 'teal',
    },
  ]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: '8px',
    }}>
      {cards.map(card => (
        <div key={card.label} style={{
          background: 'var(--panel)',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          padding: '10px 12px',
        }}>
          <div style={{
            fontSize: '9px',
            letterSpacing: '1.5px',
            color: 'var(--text-muted)',
            fontWeight: 600,
            marginBottom: '5px',
          }}>
            {card.label}
          </div>
          <div style={{
            fontSize: '14px',
            fontWeight: 700,
            color: cardColor(card.color),
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {card.value}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px' }}>
            {card.sub}
          </div>
        </div>
      ))}
    </div>
  )
}
