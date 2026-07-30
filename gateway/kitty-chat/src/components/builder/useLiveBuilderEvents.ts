'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

export interface BuilderLiveEvent {
  event_id: string
  seq: number
  timestamp: string
  type: string
  initiative_id: string
  packet_id: string
  attempt_id: string
  session_id: string
  payload: Record<string, unknown>
}

interface UseLiveBuilderEventsOptions {
  packetId?: string
  enabled?: boolean
}

export function useLiveBuilderEvents({
  packetId,
  enabled = true,
}: UseLiveBuilderEventsOptions = {}) {
  const [events, setEvents] = useState<BuilderLiveEvent[]>([])
  const [connected, setConnected] = useState(false)
  const cursorRef = useRef<number | null>(null)
  const sourceRef = useRef<EventSource | null>(null)
  const bufferRef = useRef<BuilderLiveEvent[]>([])

  const connect = useCallback(() => {
    if (!enabled) return

    const params = new URLSearchParams()
    if (packetId) params.set('packet_id', packetId)
    if (cursorRef.current !== null) params.set('cursor', String(cursorRef.current))

    const url = `/proxy/builder/events?${params.toString()}`
    const source = new EventSource(url)
    sourceRef.current = source

    source.addEventListener('connected', () => {
      setConnected(true)
    })

    source.addEventListener('message', (e: MessageEvent) => {
      try {
        const event: BuilderLiveEvent = JSON.parse(e.data)
        cursorRef.current = event.seq
        bufferRef.current = bufferRef.current.concat(event).slice(-200)
        setEvents([...bufferRef.current])
      } catch {
        // parse error — skip malformed event
      }
    })

    source.addEventListener('heartbeat', () => {
      // heartbeat — no state change needed
    })

    source.onerror = () => {
      setConnected(false)
      source.close()
      setTimeout(connect, 3000)
    }
  }, [enabled, packetId])

  useEffect(() => {
    connect()
    return () => {
      sourceRef.current?.close()
      setConnected(false)
    }
  }, [connect])

  const clear = useCallback(() => {
    bufferRef.current = []
    setEvents([])
    cursorRef.current = null
  }, [])

  return { events, connected, clear }
}
