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

export type PreflightAction = 'run' | 'blocked' | 'refuse'

export interface GatewayPreflightResult {
  action: PreflightAction
  route: string | null
  estimated_cost_cad: number
  cost_basis: string
  reasons: string[]
  packet: {
    initiative_id: string
    packet_id: string
    task_id?: string | null
    base_sha?: string | null
    current_head?: string | null
  }
  budget: {
    weekly_budget_cad: number
    remaining_cad: number
    within_budget: boolean
    basis: string
  }
  eligibility: { state: string; blocked_by?: string[] }
  data_quality: { state: string; issues?: string[] }
  dispatch_hash?: string
}

export interface GatewaySchedulerStatus {
  supported: boolean
  installed: boolean
  loaded: boolean
  healthy: boolean
  label: string
  plist_path: string
  start_interval_seconds: number | null
  run_at_load: boolean | null
  last_exit_status: number | null
  pid: number | null
  last_tick_at: string | null
  next_run_at: string | null
  reason: string | null
}

export interface GatewaySupervisorStatus {
  schema_version: number
  running: boolean
  active_runs: Array<Record<string, unknown>>
  eligible_now: number
  on_hold: number
  last_tick_at: string | null
  next_run_at: string | null
  scheduler: GatewaySchedulerStatus
  lock_path: string
  budget: Record<string, unknown>
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

function isNullableString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'string'
}

function isNullableNumberOrString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value))
}

function isNullableBoolean(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'boolean'
}

function isEvidenceField(
  evidence: Record<string, unknown>,
  section: string,
  field: string,
  predicate: (value: unknown) => boolean,
): boolean {
  const nested = evidence[section]
  return nested === undefined || nested === null || (isRecord(nested) && predicate(nested[field]))
}

function isEvidence(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) return false
  return (
    isEvidenceField(value, 'approval', 'state', isNullableString)
    && isEvidenceField(value, 'review', 'verdict', isNullableString)
    && isEvidenceField(value, 'review', 'summary', isNullableString)
    && isEvidenceField(value, 'validation', 'status', isNullableString)
    && isEvidenceField(value, 'validation', 'summary', isNullableString)
    && isEvidenceField(value, 'publication', 'pr_number', isNullableNumberOrString)
    && isEvidenceField(value, 'publication', 'checks_state', isNullableString)
    && isEvidenceField(value, 'publication', 'merged', isNullableBoolean)
    && isEvidenceField(value, 'publication', 'merged_at', isNullableString)
  )
}


function isCurrentPacket(value: unknown): boolean {
  if (value === undefined || value === null) return true
  if (!isRecord(value)) return false
  return ['id', 'title', 'objective', 'task_id', 'task_state', 'failure_kind', 'next_action', 'updated_at']
    .every(field => isNullableString(value[field]))
}

function isCurrentRun(value: unknown): boolean {
  if (value === undefined || value === null) return true
  if (!isRecord(value)) return false
  return ['id', 'state', 'started_at', 'ended_at'].every(field => isNullableString(value[field]))
}

function isWorkItem(value: unknown): value is GatewayWorkItem {
  if (!isRecord(value)) return false
  const blocker = value.blocker
  return (
    typeof value.id === 'string'
    && (typeof value.title === 'string' || value.title === null)
    && typeof value.state === 'string'
    && WORK_STATES.has(value.state as GatewayWorkState)
    && isRecord(value.source)
    && value.source.kind === 'builder'
    && typeof value.source.initiative_id === 'string'
    && isCurrentPacket(value.current_packet)
    && isCurrentRun(value.current_run)
    && isEvidence(value.evidence)
    && (value.next_action === undefined || value.next_action === null || typeof value.next_action === 'string')
    && (
      blocker === undefined
      || blocker === null
      || (isRecord(blocker) && (blocker.reason === undefined || blocker.reason === null || typeof blocker.reason === 'string'))
    )
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

function isPreflightResult(value: unknown): value is GatewayPreflightResult {
  if (!isRecord(value) || !isRecord(value.packet) || !isRecord(value.budget) || !isRecord(value.eligibility) || !isRecord(value.data_quality)) return false
  return (
    (value.action === 'run' || value.action === 'blocked' || value.action === 'refuse')
    && (value.route === null || typeof value.route === 'string')
    && typeof value.estimated_cost_cad === 'number'
    && typeof value.cost_basis === 'string'
    && Array.isArray(value.reasons)
    && value.reasons.every(reason => typeof reason === 'string')
    && typeof value.packet.initiative_id === 'string'
    && typeof value.packet.packet_id === 'string'
    && typeof value.budget.weekly_budget_cad === 'number'
    && typeof value.budget.remaining_cad === 'number'
    && typeof value.budget.within_budget === 'boolean'
    && typeof value.eligibility.state === 'string'
    && typeof value.data_quality.state === 'string'
  )
}

function isSupervisorStatus(value: unknown): value is GatewaySupervisorStatus {
  if (!isRecord(value) || !isRecord(value.scheduler)) return false
  const scheduler = value.scheduler
  return (
    value.schema_version === 1
    && typeof value.running === 'boolean'
    && Array.isArray(value.active_runs)
    && typeof value.eligible_now === 'number'
    && typeof value.on_hold === 'number'
    && typeof value.lock_path === 'string'
    && typeof scheduler.supported === 'boolean'
    && typeof scheduler.installed === 'boolean'
    && typeof scheduler.loaded === 'boolean'
    && typeof scheduler.healthy === 'boolean'
    && typeof scheduler.label === 'string'
    && typeof scheduler.plist_path === 'string'
    && (scheduler.start_interval_seconds === null || typeof scheduler.start_interval_seconds === 'number')
    && (scheduler.last_exit_status === null || typeof scheduler.last_exit_status === 'number')
    && (scheduler.reason === null || typeof scheduler.reason === 'string')
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

export async function fetchPreflight(initiativeId: string, packetId: string): Promise<GatewayPreflightResult> {
  const endpoint = `${GATEWAY_BASE}/builder/preflight/${encodeURIComponent(initiativeId)}/${encodeURIComponent(packetId)}`
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
    if (!isPreflightResult(payload)) throw new Error('Gateway preflight returned an invalid payload')
    return payload
  } finally {
    globalThis.clearTimeout(timeoutId)
  }
}

export async function fetchSupervisorStatus(): Promise<GatewaySupervisorStatus> {
  const endpoint = `${GATEWAY_BASE}/builder/supervisor`
  const response = await fetch(endpoint)
  if (!response.ok) {
    const detail = await errorDetail(response)
    throw new Error(detail || `GET ${endpoint} failed: ${response.status}`)
  }
  const payload: unknown = await response.json()
  if (!isSupervisorStatus(payload)) throw new Error('Gateway supervisor returned an invalid payload')
  return payload
}

export function useSupervisor() {
  return useQuery({
    queryKey: ['builder-supervisor'],
    queryFn: fetchSupervisorStatus,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

export function usePreflight(initiativeId: string | null, packetId: string | null) {
  return useQuery({
    queryKey: ['builder-preflight', initiativeId, packetId],
    queryFn: () => fetchPreflight(initiativeId!, packetId!),
    enabled: Boolean(initiativeId && packetId),
    staleTime: 5_000,
    refetchInterval: 10_000,
  })
}

export function useWorkSnapshot() {
  return useQuery({
    queryKey: ['work'],
    queryFn: fetchGatewayWorkSnapshot,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}
