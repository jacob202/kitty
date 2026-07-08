'use client'
import type { CSSProperties } from 'react'
import type { GatewayLoop, LoopStatus } from '@/lib/gateway'
import { Card, CardHeader, ItemCard } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { Skeleton } from './Skeleton'

interface Props {
  loops: GatewayLoop[]
  onToggle?: (loopId: string) => void
  title?: string
  isLoading?: boolean
}

function statusColor(status: LoopStatus): string {
  switch (status) {
    case 'running': return 'var(--mint)'
    case 'paused': return 'var(--orange)'
    case 'error': return 'var(--error)'
    case 'idle': return 'var(--text-muted)'
  }
}

function statusLabel(status: LoopStatus): string {
  switch (status) {
    case 'running': return 'RUNNING'
    case 'paused': return 'PAUSED'
    case 'error': return 'ERROR'
    case 'idle': return 'IDLE'
  }
}

export function LoopWatch({ loops, onToggle, title = 'Loop Watch', isLoading = false }: Props) {
  const sorted = [...loops].sort((a, b) => {
    const statusOrder = { running: 0, paused: 1, error: 2, idle: 3 }
    return (statusOrder[a.status] ?? 4) - (statusOrder[b.status] ?? 4)
  })

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <CardHeader title={title} count={`${loops.length} active`} />
      <div style={listStyle}>
        {sorted.map(loop => (
          <ItemCard key={loop.loop_id} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={cardHeaderStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: statusColor(loop.status),
                  flexShrink: 0,
                }} />
                <span style={loopNameStyle}>{loop.name}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  ...badgeStyle,
                  color: statusColor(loop.status),
                  borderColor: statusColor(loop.status),
                }}>
                  {statusLabel(loop.status)}
                </span>
                {onToggle && loop.status !== 'error' && (
                  <Button
                    variant="action"
                    onClick={() => onToggle(loop.loop_id)}
                    style={{ width: 28, height: 24, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 0 }}
                    ariaLabel={loop.status === 'running' ? 'Pause loop' : 'Start loop'}
                  >
                    {loop.status === 'running' ? '⏸' : '▶'}
                  </Button>
                )}
              </div>
            </div>
            {loop.description && (
              <div style={descStyle}>{loop.description}</div>
            )}
            <div style={metaStyle}>
              {loop.last_run && (
                <span>Last run: {new Date(loop.last_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              )}
              {loop.interval_minutes && (
                <span>· Every {loop.interval_minutes}m</span>
              )}
              {loop.error_message && (
                <span style={{ color: 'var(--error)' }}> · {loop.error_message}</span>
              )}
            </div>
          </ItemCard>
        ))}
        {loops.length === 0 && (
          isLoading ? (
            <div style={{ display: 'grid', gap: 8 }}>
              <Skeleton height={48} />
              <Skeleton height={48} />
            </div>
          ) : (
            <EmptyState>No loops configured</EmptyState>
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

const loopNameStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
}

const badgeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  border: '1px solid',
  borderRadius: 4,
  padding: '2px 6px',
  background: 'transparent',
}



const descStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 12,
  color: 'var(--text-dim)',
  lineHeight: 1.4,
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}
