'use client'
import type { CSSProperties } from 'react'
import type { GatewayLoop, LoopStatus } from '@/lib/gateway'

interface Props {
  loops: GatewayLoop[]
  onToggle?: (loopId: string) => void
  title?: string
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

export function LoopWatch({ loops, onToggle, title = 'Loop Watch' }: Props) {
  const sorted = [...loops].sort((a, b) => {
    const statusOrder = { running: 0, paused: 1, error: 2, idle: 3 }
    return (statusOrder[a.status] ?? 4) - (statusOrder[b.status] ?? 4)
  })

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>{title}</span>
        <span style={countStyle}>{loops.length} active</span>
      </div>
      <div style={listStyle}>
        {sorted.map(loop => (
          <div key={loop.loop_id} style={cardBaseStyle}>
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
                    title={loop.status === 'running' ? 'Pause loop' : 'Start loop'}
                    aria-label={loop.status === 'running' ? 'Pause loop' : 'Start loop'}
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
                <span>Last run: {new Date(loop.last_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              )}
              {loop.interval_minutes && (
                <span>· Every {loop.interval_minutes}m</span>
              )}
              {loop.error_message && (
                <span style={{ color: 'var(--error)' }}> · {loop.error_message}</span>
              )}
            </div>
          </div>
        ))}
        {loops.length === 0 && (
          <div style={emptyStyle}>No loops configured</div>
        )}
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

const headerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingBottom: 8,
  borderBottom: '1px solid var(--border-dim)',
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--text)',
  marginBottom: 4,
}

const countStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  letterSpacing: '0.05em',
}

const listStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const cardBaseStyle: CSSProperties = {
  background: 'var(--panel)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '12px 14px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
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
  textTransform: 'uppercase',
  border: '1px solid',
  borderRadius: 4,
  padding: '2px 6px',
  background: 'transparent',
}

const toggleBtnStyle = (isRunning: boolean): CSSProperties => ({
  background: 'var(--surface-mid)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  width: 28,
  height: 24,
  display: 'grid',
  placeItems: 'center',
  cursor: 'pointer',
  fontSize: 10,
  color: 'var(--text-dim)',
  transition: 'all 0.15s ease',
})

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

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-faint)',
  textAlign: 'center',
  padding: '24px 0',
  fontStyle: 'italic',
}
