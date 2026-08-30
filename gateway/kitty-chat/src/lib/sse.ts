'use client'
import { useEffect, useRef } from 'react'
import { ExpertSignal } from '@/lib/types'

const RECONNECT_BASE_MS = 1_000
const RECONNECT_MAX_MS = 30_000

/**
 * Subscribe to a gateway SSE endpoint and hand each `data:` payload to
 * `onMessage`. Reconnects with bounded exponential backoff (1s doubling to
 * 30s, reset on any received message) when the connection drops, and never
 * reconnects after unmount. `onOpen` fires on every successful (re)connect so
 * consumers can resync state that changed while the stream was down. The
 * latest callbacks are always used without resubscribing, so callers may pass
 * inline functions.
 */
export function useSSE(
  url: string | null,
  onMessage: (data: string) => void,
  onOpen?: () => void,
): void {
  const handlerRef = useRef(onMessage)
  const openRef = useRef(onOpen)
  useEffect(() => {
    handlerRef.current = onMessage
    openRef.current = onOpen
  }, [onMessage, onOpen])

  useEffect(() => {
    if (!url) return
    if (typeof EventSource === 'undefined') {
      console.warn('EventSource unavailable in this environment; SSE stream disabled')
      return
    }

    let source: EventSource | null = null
    let timer: number | null = null
    let attempts = 0
    let disposed = false

    const connect = () => {
      if (disposed) return
      source = new EventSource(url)
      source.onopen = () => {
        attempts = 0
        try {
          openRef.current?.()
        } catch (err) {
          console.error('SSE open handler failed:', err)
        }
      }
      source.onmessage = (event: MessageEvent) => {
        attempts = 0
        try {
          handlerRef.current(String(event.data))
        } catch (err) {
          // A broken handler (or malformed payload it chokes on) must not
          // kill the stream or the page — log and keep listening.
          console.error('SSE message handler failed:', err)
        }
      }
      source.onerror = () => {
        // EventSource has native retry, but its behavior varies by failure
        // mode; closing and owning the backoff keeps reconnection bounded
        // and deterministic.
        source?.close()
        source = null
        if (disposed) return
        const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempts, RECONNECT_MAX_MS)
        attempts++
        timer = window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      disposed = true
      if (timer !== null) window.clearTimeout(timer)
      source?.close()
      source = null
    }
  }, [url])
}

// ── Expert signal fetch/dismiss (consumed by SignalFeed) ─────────────────────

export async function fetchExpertSignals(): Promise<ExpertSignal[]> {
  const res = await fetch('/proxy/experts/signals/unprocessed')
  if (!res.ok) {
    throw new Error(`Gateway returned ${res.status} for expert signals`)
  }
  const json = await res.json()
  if (!Array.isArray(json?.signals)) {
    throw new Error('Gateway /experts/signals/unprocessed returned an invalid payload')
  }
  return json.signals as ExpertSignal[]
}

export async function dismissExpertSignal(id: number): Promise<void> {
  const res = await fetch(`/proxy/experts/signals/${id}/dismiss`, { method: 'POST' })
  if (!res.ok) {
    throw new Error(`Gateway returned ${res.status} dismissing signal ${id}`)
  }
}
