'use client'

import { useQuery } from '@tanstack/react-query'

const GATEWAY_BASE = '/proxy'
const DEFAULT_TIMEOUT_MS = 8000
const MAX_ERROR_DETAIL = 240

export type GatewayWorkState =
  | 'active'
  | 'paused'
  | 'failed'
  | 'blocked'
  | 'completed'
  | 'ready'
  | 'waiting'

export interface GatewayWorkQueue {
  total: number
  queued: number
  claimed: number
  running: number
  blocked: number
  pr_opened: number
  awaiting_review: number
  done: number
  failed: number
  cancelled: number
}

export interface GatewayWorkItem {
  id: string
  title: string | null
  state: GatewayWorkState
  source: { kind: 'builder'; initiative_id: string; packet_id: string | null }
  current_packet: {
    id: string | null
    title: string | null
    objective?: string | null
    task_id: string | null
    task_state: string | null
    failure_kind?: string | null
    next_action?: string | null
    updated_at?: string | null
  } | null
  current_run: {
    id: string | null
    state: string | null
    started_at?: string | null
    ended_at?: string | null
  } | null
  blocker: { state?: string; reason?: string | null; blocked_by?: string[] } | null
  next_action: string | null
  evidence: Record<string, unknown>
  data_quality: { state: string; issues?: string[] }
  updated_at: string | null
}

export interface GatewayWorkSnapshot {
  schema_version: number
  observed_at: string
  valid_until: string
  source: {
    kind: 'builder'
    state: 'available' | 'degraded'
    reason?: string | null
    [key: string]: unknown
  }
  counts: Record<GatewayWorkState | 'total', number>
  queue: GatewayWorkQueue | null
  items: GatewayWorkItem[]
  item_limit: number
  total_items: number
}

const WORK_STATES = new Set<GatewayWorkState>([
  'active', 'paused', 'failed', 'blocked', 'completed', 'ready', 'waiting',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'string'
}

function isBlocker(value: unknown): boolean {
  return value === undefined || value === null || (isRecord(value) && isOptionalString(value.reason))
}

function isEvidence(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) return false
  return ['approval', 'review', 'validation', 'publication'].every((field) => {
    const nested = value[field]
    return nested === undefined || nested === null || isRecord(nested)
  })
}

function isWorkItem(value: unknown): value is GatewayWorkItem {
  if (!isRecord(value)) return false
  return (
    typeof value.id === 'string'
    && (typeof value.title === 'string' || value.title === null)
    && typeof value.state === 'string'
    && WORK_STATES.has(value.state as GatewayWorkState)
    && isRecord(value.source)
    && value.source.kind === 'builder'
    && typeof value.source.initiative_id === 'string'
    && isOptionalString(value.next_action)
    && isBlocker(value.blocker)
    && isEvidence(value.evidence)
    && isRecord(value.data_quality)
    && typeof value.data_quality.state === 'string'
    && (
      value.data_quality.issues === undefined
      || (Array.isArray(value.data_quality.issues) && value.data_quality.issues.every(issue => typeof issue === 'string'))
    )
  )
}

function isWorkSnapshot(value: unknown): value is GatewayWorkSnapshot {
  if (!isRecord(value) || !isRecord(value.source) || !isRecord(value.counts)) return false
  return (
    value.schema_version === 1
    && typeof value.observed_at === 'string'
    && typeof value.valid_until === 'string'
    && value.source.kind === 'builder'
    && (value.source.state === 'available' || value.source.state === 'degraded')
    && Array.isArray(value.items)
    && value.items.every(isWorkItem)
    && typeof value.item_limit === 'number'
    && typeof value.total_items === 'number'
  )
}

async function errorDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json()
    if (isRecord(body) && typeof body.detail === 'string') {
      return body.detail.slice(0, MAX_ERROR_DETAIL)
    }
  } catch {
    return null
  }
  return null
}

export async function fetchGatewayWorkSnapshot(): Promise<GatewayWorkSnapshot> {
  const endpoint = `${GATEWAY_BASE}/work`
  const controller = new AbortController()
  const timeoutId = globalThis.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
  try {
    const response = await fetch(endpoint, { signal: controller.signal })
    if (!response.ok) {
      const detail = await errorDetail(response)
      const suffix = detail ? `: ${detail}` : ''
      throw new Error(`GET ${endpoint} failed: ${response.status} ${response.statusText}${suffix}`.trim())
    }
    const payload: unknown = await response.json()
    if (!isWorkSnapshot(payload)) {
      throw new Error('Gateway /work returned an invalid payload')
    }
    return payload
  } finally {
    globalThis.clearTimeout(timeoutId)
  }
}

export function useWorkSnapshot() {
  return useQuery({
    queryKey: ['work'],
    queryFn: fetchGatewayWorkSnapshot,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}
