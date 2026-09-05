'use client'

// Standalone macOS Calendar fetchers for the Dashboard view. Kept out of
// gateway.ts/queries.ts deliberately — those files are governed by the
// ui:action-grammar coordination lock, which another agent held at the time
// this shipped. Duplicating the small fetch-with-timeout helper here avoids
// waiting on that lock for an unrelated, additive feature.

import { useQuery } from '@tanstack/react-query'

const GATEWAY_BASE = '/proxy'

export interface GatewayCalendarEvent {
  title?: string
  start?: string
  start_date?: string
  start_time?: string
}

export interface GatewayCalendar {
  available: boolean
  events: GatewayCalendarEvent[]
}

export type GatewayCalendarPayload = {
  calendar: GatewayCalendar | null
  fromLiveGateway: boolean
  error: string | null
}

function describeFetchError(err: unknown, response: Response | null): string {
  if (err instanceof Error) {
    if (err.name === 'AbortError') return 'Request timed out — is the Kitty gateway running?'
    return err.message || 'Network error'
  }
  if (response && !response.ok) {
    return `Gateway returned ${response.status} ${response.statusText}`.trim()
  }
  return 'Could not reach the gateway'
}

async function fetchWithTimeout(input: string, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { signal: controller.signal })
  } finally {
    window.clearTimeout(timeoutId)
  }
}

async function fetchGatewayCalendar(path: string): Promise<GatewayCalendarPayload> {
  try {
    // Backend's own osascript call allows 15s (calendar_integration.py); stay above that
    // so a healthy-but-slow Calendar lookup doesn't get reported as a timeout.
    const response = await fetchWithTimeout(`${GATEWAY_BASE}${path}`, 16000)
    if (!response.ok) {
      return { calendar: null, fromLiveGateway: false, error: describeFetchError(null, response) }
    }
    const calendar = (await response.json()) as GatewayCalendar
    return { calendar, fromLiveGateway: true, error: null }
  } catch (err) {
    return { calendar: null, fromLiveGateway: false, error: describeFetchError(err, null) }
  }
}

export function useGatewayCalendarToday() {
  return useQuery({
    queryKey: ['calendar', 'today'],
    queryFn: () => fetchGatewayCalendar('/calendar/today'),
    refetchInterval: 5 * 60_000,
  })
}

export function useGatewayCalendarUpcoming(days = 7) {
  return useQuery({
    queryKey: ['calendar', 'upcoming', days],
    queryFn: () => fetchGatewayCalendar(`/calendar/upcoming?days=${days}`),
    refetchInterval: 15 * 60_000,
  })
}
