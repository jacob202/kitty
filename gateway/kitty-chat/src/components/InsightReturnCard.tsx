'use client'
import { useState, type CSSProperties } from 'react'
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState, bodyText } from '@/lib/ui'
import { useInsightLoopDue, useRespondToLoopInsight } from '@/lib/queries'
import type { GatewayLoopInsight, LoopInsightChoice } from '@/lib/gateway'
import { Skeleton } from './Skeleton'

/** IL-03: surfaces due insight-loop items so Jacob can act, snooze, or
 *  archive them from the home dashboard (issue #270). Renders nothing when
 *  nothing is due — an empty loop is the normal state, not a banner. */
export function InsightReturnCard() {
  const due = useInsightLoopDue()
  const respond = useRespondToLoopInsight()
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (due.isPending) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>back to you</span>
        </div>
        <Skeleton height={56} />
      </div>
    )
  }

  if (due.isError) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>back to you</span>
        </div>
        <div role="alert" style={{ ...emptyState, color: 'var(--c-red)' }}>
          insight loop unavailable
        </div>
      </div>
    )
  }

  const items = due.data ?? []
  if (items.length === 0) return null

  const handle = async (item: GatewayLoopInsight, choice: LoopInsightChoice) => {
    setBusyId(item.id)
    setError(null)
    try {
      const opts =
        choice === 'snooze'
          ? { snoozeUntil: nextMorningIso() }
          : choice === 'archive'
            ? { archiveReason: 'not_useful' }
            : {}
      await respond.mutateAsync({ itemId: item.id, choice, ...opts })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'respond failed')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>back to you</span>
        <span style={countStyle}>{items.length} to revisit</span>
      </div>
      {items.map((item) => {
        const p = item.payload
        const isBusy = busyId === item.id
        return (
          <div key={item.id} style={itemStyle}>
            <div style={metaRowStyle}>
              <span style={badgeStyle}>{p.category}</span>
              <span style={metaTextStyle}>
                {p.returned_count > 0 ? `surfaced ${p.returned_count}×` : 'first return'}
              </span>
            </div>
            <div style={{ ...bodyText, fontSize: 13, color: 'var(--ink)' }}>{p.summary}</div>
            <div style={actionsStyle}>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void handle(item, 'act')}
                aria-label={`Act on: ${p.summary}`}
                style={{ ...primaryBtnStyle, opacity: isBusy ? 0.5 : 1 }}
              >
                {isBusy ? '…' : 'act'}
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void handle(item, 'snooze')}
                aria-label={`Snooze until tomorrow: ${p.summary}`}
                style={{ ...btnStyle, opacity: isBusy ? 0.5 : 1 }}
              >
                snooze
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void handle(item, 'archive')}
                aria-label={`Archive: ${p.summary}`}
                style={{ ...btnStyle, opacity: isBusy ? 0.5 : 1 }}
              >
                archive
              </button>
            </div>
          </div>
        )
      })}
      {error && (
        <div role="alert" style={{ ...bodyText, fontSize: 11, color: 'var(--c-red)' }}>
          {error}
        </div>
      )}
    </div>
  )
}

/** Snooze target: tomorrow 08:00 local, as an ISO datetime for the gateway. */
function nextMorningIso(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(8, 0, 0, 0)
  return d.toISOString()
}

const containerStyle: CSSProperties = { ...card, display: 'flex', flexDirection: 'column', gap: 12 }
const headerStyle: CSSProperties = cardHeader
const titleStyle: CSSProperties = cardTitle
const countStyle: CSSProperties = cardMeta

const itemStyle: CSSProperties = {
  ...itemCard,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const metaRowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
}

const badgeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  border: '1px solid var(--cat-ginger)',
  borderRadius: 4,
  padding: '2px 6px',
  color: 'var(--cat-ginger)',
}

const metaTextStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const actionsStyle: CSSProperties = {
  display: 'flex',
  gap: 6,
}

const primaryBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  padding: '4px 12px',
  borderRadius: 4,
  border: 'none',
  cursor: 'pointer',
  background: 'var(--primary)',
  color: 'var(--on-primary)',
}

const btnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  padding: '4px 12px',
  borderRadius: 4,
  border: '1px solid var(--line)',
  cursor: 'pointer',
  background: 'transparent',
  color: 'var(--ink-2)',
}
