'use client'
import type { CSSProperties } from 'react'
import type { GatewayInsight, InsightKind } from '@/lib/gateway'

interface Props {
  insights: GatewayInsight[]
  onDismiss?: (insightId: string) => void
  onAction?: (insightId: string, actionId: string) => void
  title?: string
}

function kindColor(kind: InsightKind): string {
  switch (kind) {
    case 'pattern':    return 'var(--teal)'
    case 'anomaly':    return 'var(--error)'
    case 'suggestion': return 'var(--orange)'
    case 'milestone':  return 'var(--mint)'
  }
}

function kindLabel(kind: InsightKind): string {
  switch (kind) {
    case 'pattern':    return 'pattern'
    case 'anomaly':    return 'anomaly'
    case 'suggestion': return 'suggestion'
    case 'milestone':  return 'milestone'
  }
}

function timeAgo(ts: number): string {
  const diff = (Date.now() - ts * 1000) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function InsightFeed({ insights, onDismiss, onAction, title = 'Insights' }: Props) {
  const sorted = [...insights].sort((a, b) => b.created_at - a.created_at)

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={headerTitleStyle}>{title}</span>
        <span style={countStyle}>{insights.length} new</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingBottom: 4 }}>
        {sorted.map(insight => {
          const kColor = kindColor(insight.kind)
          return (
            <div
              key={insight.insight_id}
              style={{
                borderLeft: `2px solid ${kColor}`,
                padding: '10px 14px',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                borderRadius: '0 6px 6px 0',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: kColor, flexShrink: 0,
                  }} />
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                    letterSpacing: '0.1em', textTransform: 'uppercase' as const,
                    color: kColor, border: `1px solid ${kColor}`,
                    borderRadius: 3, padding: '1px 5px',
                  }}>
                    {kindLabel(insight.kind)}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-ghost)',
                  }}>
                    {timeAgo(insight.created_at)}
                  </span>
                  {onDismiss && (
                    <span
                      onClick={() => onDismiss(insight.insight_id)}
                      style={{
                        color: 'var(--text-ghost)', fontSize: 10, cursor: 'pointer',
                        padding: '0 2px', lineHeight: 1,
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        letterSpacing: '0.04em',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-muted)')}
                      onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-ghost)')}
                    >
                      Dismiss
                    </span>
                  )}
                </div>
              </div>

              <div style={{
                fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600,
                color: 'var(--text)', lineHeight: 1.3,
              }}>
                {insight.title}
              </div>

              {insight.detail && (
                <div style={{
                  fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--text-dim)',
                  lineHeight: 1.4,
                }}>
                  {insight.detail}
                </div>
              )}

              {insight.source && (
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 10,
                  color: 'var(--text-ghost)', fontStyle: 'italic',
                }}>
                  {insight.source}
                </div>
              )}

              {insight.actions && insight.actions.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const, marginTop: 4 }}>
                  {insight.actions.map(action => (
                    <button
                      key={action.action_id}
                      onClick={() => onAction?.(insight.insight_id, action.action_id)}
                      style={{
                        background: 'var(--surface-mid)',
                        border: '1px solid var(--border)',
                        borderRadius: 4,
                        padding: '3px 10px',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        letterSpacing: '0.03em',
                      }}
                      onMouseEnter={e => {
                        const el = e.currentTarget as HTMLButtonElement
                        el.style.color = 'var(--text)'
                        el.style.borderColor = kColor
                      }}
                      onMouseLeave={e => {
                        const el = e.currentTarget as HTMLButtonElement
                        el.style.color = 'var(--text-muted)'
                        el.style.borderColor = 'var(--border)'
                      }}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {insights.length === 0 && (
          <div style={emptyStyle}>No new insights</div>
        )}
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  paddingTop: 14,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  overflow: 'hidden',
}

const headerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '0 14px 10px',
  borderBottom: '1px solid var(--border-dim)',
}

const headerTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  color: 'var(--text-muted)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
}

const countStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-ghost)',
  letterSpacing: '0.05em',
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
  padding: '20px 0',
  fontStyle: 'italic',
}
