'use client'

import { useEffect, useState } from 'react'
import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useKittyRuntime, type KittyRuntimeOptions } from '@/lib/kitty-runtime'

interface Props extends KittyRuntimeOptions {
  children: React.ReactNode
}

const HEALTH_TIMEOUT_MS = 4000

function HealthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<'checking' | 'ok' | 'down'>('checking')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), HEALTH_TIMEOUT_MS)

    fetch('/proxy/health', { signal: ctrl.signal })
      .then(r => {
        if (cancelled) return
        if (!r.ok) throw new Error(`Gateway returned ${r.status}`)
        setState('ok')
      })
      .catch(e => {
        if (cancelled) return
        const msg = e.name === 'AbortError'
          ? 'Request timed out — is the Kitty gateway running?'
          : (e.message || 'Could not reach the gateway')
        setError(msg)
        setState('down')
      })
      .finally(() => clearTimeout(timer))

    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

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
          : `Gateway offline — run \`./kitty up\`${error ? `\n${error}` : ''}`}
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
