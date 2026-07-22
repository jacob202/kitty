'use client'
import type { ReactNode } from 'react'
import { Card } from './Card'
import { Button } from './Button'
import { StatusBadge, type StatusState } from './StatusBadge'
import { AlertTriangle, WifiOff, RefreshCw, Database, SearchX, ShieldAlert } from 'lucide-react'

export interface AsyncStateProps {
  state: 'loading' | 'empty' | 'degraded' | 'unavailable' | 'stale' | 'error' | 'retrying' | 'partial' | 'forbidden'
  title?: string
  message?: string
  onRetry?: () => void
  onReconnect?: () => void
  children?: ReactNode
}

const DEFAULT_TITLES: Record<AsyncStateProps['state'], string> = {
  loading: 'Loading…',
  empty: 'Nothing here yet',
  degraded: 'Running with limited capability',
  unavailable: 'Unavailable',
  stale: 'Showing cached data',
  error: 'Something went wrong',
  retrying: 'Retrying…',
  partial: 'Partial results',
  forbidden: 'Permission needed',
}

const DEFAULT_MESSAGES: Record<AsyncStateProps['state'], string> = {
  loading: 'Getting the latest data for you.',
  empty: "There isn't anything to show here right now.",
  degraded: 'Some data sources are not available. What is shown may be incomplete.',
  unavailable: "This service isn't reachable right now.",
  stale: 'The last known data is shown below. It may be out of date.',
  error: "Kitty couldn't load this data. The issue may be temporary.",
  retrying: 'Trying to reach the service again.',
  partial: 'Some results could not be loaded.',
  forbidden: "Kitty doesn't have permission to access this.",
}

const ICONS: Record<AsyncStateProps['state'], ReactNode> = {
  loading: <StatusBadge state="working" variant="dot" />,
  empty: <SearchX size={20} style={{ color: 'var(--ink-2)', opacity: 0.5 }} />,
  degraded: <AlertTriangle size={20} style={{ color: 'var(--c-yellow)' }} />,
  unavailable: <WifiOff size={20} style={{ color: 'var(--c-red)' }} />,
  stale: <Database size={20} style={{ color: 'var(--ink-2)' }} />,
  error: <AlertTriangle size={20} style={{ color: 'var(--c-red)' }} />,
  retrying: <RefreshCw size={20} style={{ color: 'var(--c-yellow)', animation: 'throb 1.1s ease-in-out infinite' }} />,
  partial: <Database size={20} style={{ color: 'var(--c-yellow)' }} />,
  forbidden: <ShieldAlert size={20} style={{ color: 'var(--c-red)' }} />,
}

export function AsyncState({
  state,
  title,
  message,
  onRetry,
  onReconnect,
  children,
}: AsyncStateProps) {
  const defaultTitle = title ?? DEFAULT_TITLES[state]
  const defaultMessage = message ?? DEFAULT_MESSAGES[state]
  const icon = ICONS[state]

  return (
    <Card padding="lg" style={{ textAlign: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
        <div style={{ marginBottom: 4 }}>{icon}</div>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 16,
          fontWeight: 700,
          color: 'var(--ink)',
        }}>
          {defaultTitle}
        </div>
        <div style={{
          fontSize: 13,
          color: 'var(--ink-2)',
          lineHeight: 1.5,
          maxWidth: 320,
        }}>
          {defaultMessage}
        </div>
        {(onRetry || onReconnect) && (
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            {onRetry && (
              <Button variant="secondary" size="sm" onClick={onRetry} icon={<RefreshCw size={13} />}>
                retry
              </Button>
            )}
            {onReconnect && (
              <Button variant="primary" size="sm" onClick={onReconnect} icon={<WifiOff size={13} />}>
                reconnect
              </Button>
            )}
          </div>
        )}
        {children}
      </div>
    </Card>
  )
}
