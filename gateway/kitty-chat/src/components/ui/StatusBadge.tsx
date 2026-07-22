'use client'
import { type ReactNode, type CSSProperties } from 'react'

export type StatusState =
  | 'working' | 'needs_user' | 'scheduled' | 'paused'
  | 'failed' | 'completed' | 'unavailable' | 'degraded' | 'canceled'

const STATUS_CONFIG: Record<StatusState, { label: string; color: string }> = {
  working:     { label: 'working',   color: 'var(--c-yellow)' },
  needs_user:  { label: 'needs you', color: 'var(--c-yellow)' },
  scheduled:   { label: 'scheduled', color: 'var(--c-blue)' },
  paused:      { label: 'paused',    color: 'var(--ink-2)' },
  failed:      { label: 'failed',    color: 'var(--c-red)' },
  completed:   { label: 'done',      color: 'var(--c-green)' },
  unavailable: { label: 'offline',   color: 'var(--c-red)' },
  degraded:    { label: 'limited',   color: 'var(--c-yellow)' },
  canceled:    { label: 'canceled',  color: 'var(--ink-2)' },
}

export interface StatusBadgeProps {
  state: StatusState
  variant?: 'dot' | 'pill'
  label?: string
  compact?: boolean
}

export function StatusBadge({ state, variant = 'pill', label, compact }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[state]
  const text = label ?? cfg.label
  const isAnimated = state === 'working'

  if (variant === 'dot' || compact) {
    return (
      <span
        role="status"
        aria-label={text}
        title={text}
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: cfg.color,
          flexShrink: 0,
          ...(isAnimated ? { animation: 'throb 1.1s ease-in-out infinite' } : {}),
        }}
      />
    )
  }

  return (
    <span
      role="status"
      aria-label={text}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '2px 8px',
        borderRadius: 999,
        border: `1px solid ${cfg.color}`,
        color: cfg.color,
        fontSize: 12,
        fontWeight: 500,
        fontFamily: 'var(--font-body)',
        whiteSpace: 'nowrap',
      }}
    >
      <span style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: cfg.color,
        flexShrink: 0,
        ...(isAnimated ? { animation: 'throb 1.1s ease-in-out infinite' } : {}),
      }} />
      {text}
    </span>
  )
}
