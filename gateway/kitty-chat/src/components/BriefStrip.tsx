'use client'
import { card, sectionLabel } from '@/lib/ui'

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
  emphasis?: boolean
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
    },
    {
      label: 'NEXT UP',
      value: intention?.trim() || '—',
      sub: intention ? 'from brief' : 'waiting on gateway',
    },
    {
      label: 'OVERDUE',
      value: overdueCount > 0 ? String(overdueCount) : '—',
      sub: overdueCount > 0 ? `${overdueCount} open todo${overdueCount === 1 ? '' : 's'}` : 'nothing flagged',
      emphasis: overdueCount > 0,
    },
    {
      label: 'FOCUS',
      value: focusText?.trim() || '—',
      sub: focusText ? 'active todo' : 'see compass',
    },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      {cards.map(c => (
        <div key={c.label} style={{ ...card, padding: '12px 14px' }}>
          <div style={{ ...sectionLabel, marginBottom: 6 }}>{c.label}</div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 15,
            fontWeight: 600,
            color: c.emphasis ? 'var(--error)' : 'var(--text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: 1.2,
          }}>
            {c.value}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            {c.sub}
          </div>
        </div>
      ))}
    </div>
  )
}
