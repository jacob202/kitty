'use client'
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { GATEWAY_BASE } from '@/lib/gateway'

export function SSEListener() {
  const qc = useQueryClient()

  useEffect(() => {
    let evtSource: EventSource | null = null
    let reconnectTimeout: ReturnType<typeof setTimeout>

    function connect() {
      if (evtSource) return

      // Use GATEWAY_BASE to connect to the SSE endpoint
      evtSource = new EventSource(`${GATEWAY_BASE}/stream`)

      evtSource.onmessage = (event) => {
        const msg = event.data
        if (msg === 'knowledge_updated') {
          qc.invalidateQueries({ queryKey: ['knowledge', 'sources'] })
        } else if (msg === 'projects_updated') {
          qc.invalidateQueries({ queryKey: ['projects'] })
        } else if (msg === 'state_updated') {
          qc.invalidateQueries({ queryKey: ['state'] })
          qc.invalidateQueries({ queryKey: ['expertSignals'] })
        }
      }

      evtSource.addEventListener('connected', () => {
        console.log('[SSE] Connected to Gateway')
      })

      evtSource.onerror = () => {
        console.warn('[SSE] Connection lost, reconnecting in 5s...')
        evtSource?.close()
        evtSource = null
        reconnectTimeout = setTimeout(connect, 5000)
      }
    }

    // Only connect if we are in the browser
    if (typeof window !== 'undefined') {
      connect()
    }

    return () => {
      clearTimeout(reconnectTimeout)
      if (evtSource) {
        evtSource.close()
        evtSource = null
      }
    }
  }, [qc])

  return null
}
