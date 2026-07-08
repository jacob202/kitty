'use client'
import type { CSSProperties } from 'react'
import type { GatewayInsight, InsightKind } from '@/lib/gateway'
import { Card, CardHeader, ItemCard } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { Skeleton } from './Skeleton'

interface Props {
  insights: GatewayInsight[]
  onDismiss?: (insightId: string) => void
  onAction?: (insightId: string, actionId: string) => void
  title?: string
  isLoading?: boolean
}

function kindColor(kind: InsightKind): string {
  switch (kind) {
    case 'pattern': return 'var(--teal)'
    case 'anomaly': return 'var(--error)'
    case 'suggestion': return 'var(--orange)'
    case 'milestone': return 'var(--mint)'
  }
}

function kindLabel(kind: InsightKind): string {
  switch (kind) {
    case 'pattern': return 'PATTERN'
    case 'anomaly': return 'ANOMALY'
    case 'suggestion': return 'SUGGESTION'
    case 'milestone': return 'MILESTONE'
  }
}

function timeAgo(ts: number): string {
  const diff = (Date.now() - ts * 1000) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function InsightFeed({ insights, onDismiss, onAction, title = 'Insights', isLoading = false }: Props) {
  const sorted = [...insights].sort((a, b) => b.created_at - a.created_at)

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <CardHeader title={title} count={`${insights.length} new`} />
      <div style={listStyle}>
        {sorted.map(insight => (
          <ItemCard key={insight.insight_id} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={cardHeaderStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: kindColor(insight.kind),
                  flexShrink: 0,
                }} />
                <span style={kindBadgeStyle(kindColor(insight.kind))}>
                  {kindLabel(insight.kind)}
                </span>
              </div>
              <span style={timeStyle}>{timeAgo(insight.created_at)}</span>
            </div>
            <div style={insightTitleStyle}>{insight.title}</div>
            {insight.detail && (
              <div style={insightDetailStyle}>{insight.detail}</div>
            )}
            {insight.source && (
              <div style={sourceStyle}>Source: {insight.source}</div>
            )}
            {insight.actions && insight.actions.length > 0 && (
              <div style={actionsStyle}>
                {insight.actions.map(action => (
                  <Button
                    key={action.action_id}
                    onClick={() => onAction?.(insight.insight_id, action.action_id)}
                    variant="action"
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            )}
            {onDismiss && (
              <button
                onClick={() => onDismiss(insight.insight_id)}
                style={dismissBtnStyle}
                title="Dismiss"
                aria-label="Dismiss"
              >
                ✕
              </button>
            )}
          </ItemCard>
        ))}
        {insights.length === 0 && (
          isLoading ? (
            <div style={{ display: 'grid', gap: 8 }}>
              <Skeleton height={56} />
              <Skeleton height={56} />
            </div>
          ) : (
            <EmptyState>No new insights</EmptyState>
          )
        )}
      </div>
    </Card>
  )
}



const listStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}



const cardHeaderStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}

const kindBadgeStyle = (color: string): CSSProperties => ({
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  border: `1px solid ${color}`,
  borderRadius: 4,
  padding: '2px 6px',
  background: 'transparent',
  color,
})

const timeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
}

const insightTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--text)',
  marginTop: 2,
}

const insightDetailStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 12,
  color: 'var(--text-dim)',
  lineHeight: 1.4,
}

const sourceStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontStyle: 'italic',
}

const actionsStyle: CSSProperties = {
  display: 'flex',
  gap: 6,
  flexWrap: 'wrap',
  marginTop: 4,
}



const dismissBtnStyle: CSSProperties = {
  position: 'absolute',
  top: 8,
  right: 8,
  background: 'transparent',
  border: 'none',
  color: 'var(--text-ghost)',
  cursor: 'pointer',
  fontSize: 12,
  padding: 2,
  lineHeight: 1,
}
