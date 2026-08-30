'use client'

import { useEffect, useState } from 'react'
import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useKittyRuntime, type KittyRuntimeOptions } from '@/lib/kitty-runtime'

interface Props extends KittyRuntimeOptions {
  children: React.ReactNode
}

const HEALTH_TIMEOUT_MS = 4000
const HEALTH_RETRY_MS = 5000

function HealthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<'checking' | 'ok' | 'down'>('checking')
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    const ctrl = new AbortController()
    const timeout = setTimeout(() => ctrl.abort(), HEALTH_TIMEOUT_MS)
    let retry: ReturnType<typeof setTimeout> | undefined

    setState('checking')
    setError(null)

    fetch('/proxy/health', { signal: ctrl.signal })
      .then(r => {
        if (cancelled) return
        if (!r.ok) throw new Error('Kitty is temporarily unavailable')
        setState('ok')
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        const error = cause instanceof Error ? cause : new Error('Could not reach the gateway')
        const msg = error.name === 'AbortError'
          ? 'Connection timed out.'
          : (error.message || 'Kitty is temporarily unavailable')
        setError(msg)
        setState('down')
        retry = setTimeout(() => setAttempt(current => current + 1), HEALTH_RETRY_MS)
      })
      .finally(() => clearTimeout(timeout))

    return () => {
      cancelled = true
      ctrl.abort()
      clearTimeout(timeout)
      if (retry) clearTimeout(retry)
    }
  }, [attempt])

  if (state === 'ok') return <>{children}</>

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100dvh', width: '100vw', background: 'var(--bg)', color: 'var(--ink)',
      fontFamily: 'var(--font-body)', flexDirection: 'column', gap: '1rem',
    }}>
      <div style={{ fontSize: '2rem', opacity: 0.6 }}>Kitty</div>
      <div style={{ fontSize: '0.9rem', opacity: 0.5, textAlign: 'center', maxWidth: 320 }}>
        {state === 'checking'
          ? 'Connecting to Kitty...'
          : `Kitty is offline — trying to reconnect automatically.${error ? `\n${error}` : ''}\nIf this keeps happening, reopen Kitty.`}
      </div>
    </div>
  )
}

export function KittyRuntimeProvider({ children, ...runtimeOptions }: Props) {
  const runtime = useKittyRuntime(runtimeOptions)
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <HealthGate>{children}</HealthGate>
    </AssistantRuntimeProvider>
  )
}
