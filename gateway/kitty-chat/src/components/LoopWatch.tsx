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
    case 'paused':  return 'var(--orange)'
    case 'error':   return 'var(--error)'
    case 'idle':    return 'var(--text-muted)'
  }
}

function statusLabel(status: LoopStatus): string {
  switch (status) {
    case 'running': return 'running'
    case 'paused':  return 'paused'
    case 'error':   return 'error'
    case 'idle':    return 'idle'
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
        <span style={headerTitleStyle}>{title}</span>
        <span style={countStyle}>{loops.length} active</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {sorted.map(loop => {
          const sColor = statusColor(loop.status)
          return (
            <div
              key={loop.loop_id}
              style={{
                borderLeft: `2px solid ${sColor}`,
                padding: '10px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                borderRadius: '0 6px 6px 0',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600,
                    color: 'var(--text)',
                  }}>
                    {loop.name}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                    letterSpacing: '0.08em', textTransform: 'uppercase' as const,
                    color: sColor, border: `1px solid ${sColor}`,
                    borderRadius: 3, padding: '1px 5px',
                  }}>
                    {statusLabel(loop.status)}
                  </span>

                  {onToggle && loop.status !== 'error' && (
                    <button
                      onClick={() => onToggle(loop.loop_id)}
                      title={loop.status === 'running' ? 'Pause loop' : 'Start loop'}
                      style={{
                        background: 'var(--surface-mid)',
                        border: '1px solid var(--border)',
                        borderRadius: 4,
                        padding: '2px 8px',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        letterSpacing: '0.04em',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={e => {
                        const el = e.currentTarget as HTMLButtonElement
                        el.style.color = 'var(--text)'
                        el.style.borderColor = 'var(--border-soft)'
                      }}
                      onMouseLeave={e => {
                        const el = e.currentTarget as HTMLButtonElement
                        el.style.color = 'var(--text-muted)'
                        el.style.borderColor = 'var(--border)'
                      }}
                    >
                      {loop.status === 'running' ? 'pause' : 'run'}
                    </button>
                  )}
                </div>
              </div>

              {loop.description && (
                <div style={{
                  fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--text-dim)',
                  lineHeight: 1.4, paddingLeft: 15,
                }}>
                  {loop.description}
                </div>
              )}

              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-ghost)',
                display: 'flex', flexWrap: 'wrap' as const, gap: 4, paddingLeft: 15,
              }}>
                {loop.last_run && (
                  <span>last {new Date(loop.last_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                )}
                {loop.interval_minutes && (
                  <span>· every {loop.interval_minutes}m</span>
                )}
                {loop.error_message && (
                  <span style={{ color: 'var(--error)' }}>· {loop.error_message}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {loops.length === 0 && (
        <div style={emptyStyle}>No loops configured</div>
      )}
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  paddingTop: 14,
  paddingBottom: 8,
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
