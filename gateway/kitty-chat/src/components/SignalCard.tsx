'use client'
import { useCallback, useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { ExpertSignal } from '@/lib/types'
import { useSSE, fetchExpertSignals, dismissExpertSignal } from '@/lib/sse'

/**
 * Live proactive-signal surface (CR-03). Fetches unprocessed expert
 * suggestions and refetches whenever the gateway broadcasts `state_updated`
 * on /stream, so new signals appear without a reload. Refetching replaces the
 * whole id-keyed list, which makes duplicate stream deliveries harmless.
 */
export function SignalFeed({ compact = false }: { compact?: boolean }) {
  const [signals, setSignals] = useState<ExpertSignal[]>([])

  const refresh = useCallback(async () => {
    try {
      const list = await fetchExpertSignals()
      setSignals(list.filter((s) => s.kind === 'expert.suggestion'))
    } catch (err) {
      // Keep the last known signals; the stream will trigger another fetch.
      console.error('expert signal refresh failed:', err)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleStreamMessage = useCallback(
    (data: string) => {
      if (data === 'state_updated') void refresh()
    },
    [refresh],
  )
  const handleStreamOpen = useCallback(() => {
    // Resync on every (re)connect: signals emitted while the stream was down
    // broadcast nothing we can hear, so the open itself is the catch-up cue.
    void refresh()
  }, [refresh])
  useSSE('/proxy/stream', handleStreamMessage, handleStreamOpen)

  const handleDismiss = useCallback(async (id: number) => {
    await dismissExpertSignal(id)
    setSignals((prev) => prev.filter((s) => s.id !== id))
  }, [])

  if (!signals.length) return null
  return (
    <div
      aria-label="Proactive signals"
      aria-live="polite"
      style={{
        flexShrink: 0,
        maxHeight: 200,
        overflowY: 'auto',
        borderBottom: '1px solid var(--line)',
        background: 'var(--surface)',
        padding: compact ? '8px 12px' : '8px 22px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {signals.map((signal) => (
        <SignalCard key={signal.id} signal={signal} onDismiss={handleDismiss} />
      ))}
    </div>
  )
}

export function SignalCard({
  signal,
  onDismiss,
}: {
  signal: ExpertSignal
  onDismiss: (id: number) => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const expert = signal.source.startsWith('expert.')
    ? signal.source.slice('expert.'.length)
    : signal.source
  const headline = signal.payload.headline ?? signal.kind
  const body = signal.payload.analysis || signal.payload.action || ''
  const time = new Date(signal.ts * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })

  const handleDismiss = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await onDismiss(signal.id)
      // On success the card unmounts via the parent's list update.
    } catch (err) {
      setBusy(false)
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div
      style={{
        border: '1.5px solid var(--line)',
        borderLeft: '3px solid var(--c-yellow)',
        borderRadius: 10,
        background: 'var(--bg)',
        padding: '8px 10px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
      }}
    >
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ ...monoMetaStyle, display: 'flex', gap: 8 }}>
          <span>signal · {expert}</span>
          <span style={{ opacity: 0.7 }}>{time}</span>
        </div>
        <div
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--ink)',
            lineHeight: 1.4,
          }}
        >
          {headline}
        </div>
        {body && (
          <div
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 12,
              color: 'var(--ink-2)',
              lineHeight: 1.45,
              whiteSpace: 'pre-wrap',
            }}
          >
            {body}
          </div>
        )}
        {error && (
          <div role="alert" style={{ ...monoMetaStyle, color: 'var(--c-red)' }}>
            dismiss failed — {error}
          </div>
        )}
      </div>
      <button
        onClick={() => void handleDismiss()}
        disabled={busy}
        aria-label={`Dismiss signal: ${headline}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 34,
          height: 34,
          flexShrink: 0,
          border: 'none',
          borderRadius: 8,
          background: 'transparent',
          color: 'var(--ink-2)',
          cursor: busy ? 'default' : 'pointer',
          fontSize: 15,
          opacity: busy ? 0.5 : 1,
        }}
      >
        ✕
      </button>
    </div>
  )
}

const monoMetaStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}
