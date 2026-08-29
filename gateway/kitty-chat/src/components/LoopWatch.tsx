'use client'
import type { CSSProperties } from 'react'
import type { GatewayLoop, LoopStatus } from '@/lib/gateway'
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState } from '@/lib/ui'
import { Skeleton } from './Skeleton'

interface Props {
  loops: GatewayLoop[]
  onToggle?: (loopId: string) => void
  title?: string
  isLoading?: boolean
}

function statusColor(status: LoopStatus): string {
  switch (status) {
    case 'running': return 'var(--color-success)'
    case 'paused': return 'var(--color-warning)'
    case 'error': return 'var(--color-destructive)'
    case 'idle': return 'var(--color-text-muted)'
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

  const runningCount = loops.filter(loop => loop.status === 'running').length

  return (
    <div style={containerStyle}>
      {title ? (
        <div style={headerStyle}>
          <span style={titleStyle}>{title}</span>
          <span style={countStyle}>{runningCount} running · {loops.length} total</span>
        </div>
      ) : (
        <div style={embeddedCountStyle}>{runningCount} running · {loops.length} total</div>
      )}
      <div data-testid="automation-loop-list" style={listStyle}>
        {sorted.map(loop => (
          <div key={loop.loop_id} data-testid="automation-loop-row" style={cardBaseStyle}>
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
                  <button
                    onClick={() => onToggle(loop.loop_id)}
                    style={toggleBtnStyle(loop.status === 'running')}
                    title={loop.status === 'running' ? 'pause loop' : 'start loop'}
                    aria-label={loop.status === 'running' ? 'pause loop' : 'start loop'}
                  >
                    {loop.status === 'running' ? '⏸' : '▶'}
                  </button>
                )}
              </div>
            </div>
            {loop.description && (
              <div style={descStyle}>{loop.description}</div>
            )}
            <div style={metaStyle}>
              {loop.last_run && (
                <span>last run: {new Date(loop.last_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              )}
              {loop.interval_minutes && (
                <span>· Every {loop.interval_minutes}m</span>
              )}
              {loop.error_message && (
                <span style={{ color: 'var(--c-red)' }}> · {loop.error_message}</span>
              )}
            </div>
          </div>
        ))}
        {loops.length === 0 && (
          isLoading ? (
            <div style={{ display: 'grid', gap: 8 }}>
              <Skeleton height={48} />
              <Skeleton height={48} />
            </div>
          ) : (
            <div style={emptyStyle}>no loops configured</div>
          )
        )}
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10 }
const headerStyle: CSSProperties = cardHeader
const titleStyle: CSSProperties = cardTitle
const countStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-muted)' }
const embeddedCountStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }

const listStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  overflow: 'hidden',
}

const cardBaseStyle: CSSProperties = { padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 6, borderBottom: '1px solid var(--color-separator)' }

const cardHeaderStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}

const loopNameStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--color-text-primary)',
}

const badgeStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  border: '1px solid',
  borderRadius: 999,
  padding: '2px 6px',
  background: 'transparent',
}

const toggleBtnStyle = (_isRunning: boolean): CSSProperties => ({
  minWidth: 44,
  minHeight: 44,
  display: 'grid',
  placeItems: 'center',
  background: 'transparent',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)',
  cursor: 'pointer',
  fontSize: 13,
  color: 'var(--color-text-secondary)',
})

const descStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--color-text-secondary)',
  lineHeight: 1.4,
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  color: 'var(--color-text-muted)',
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

const emptyStyle: CSSProperties = emptyState
