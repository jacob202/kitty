'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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
  preflight: GatewayPreflight | null
  evidence: Record<string, unknown>
  data_quality: { state: string; issues?: string[] }
  updated_at: string | null
}

export interface GatewayPreflight {
  can_proceed: boolean
  blockers: string[]
  warnings: string[]
  route: string | null
  estimated_cost_cad: number
  basis: string
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
  historical_items?: number
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
  const preflight = value.preflight
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
      preflight === undefined
      || preflight === null
      || (
        isRecord(preflight)
        && typeof preflight.can_proceed === 'boolean'
        && Array.isArray(preflight.blockers)
        && Array.isArray(preflight.warnings)
        && (preflight.route === undefined || preflight.route === null || typeof preflight.route === 'string')
        && typeof preflight.estimated_cost_cad === 'number'
        && typeof preflight.basis === 'string'
      )
    )
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
    && (value.historical_items === undefined || (typeof value.historical_items === 'number' && Number.isFinite(value.historical_items) && value.historical_items >= 0))
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

export interface GatewaySupervisor {
  schema_version: number
  running: boolean
  active_runs: unknown[]
  eligible_now: number
  on_hold: number
  last_tick_at: string | null
  lock_path: string | null
  budget: {
    weekly_budget_cad: number
    estimated_spend_cad: number
    remaining_cad: number
    runs: number
    retries: number
    basis: string
  }
}

export interface BuilderCommandResult {
  ok: boolean
  action?: string
  error: string | null
  detail?: unknown
}

export interface BuilderCommand {
  action: 'requeue' | 'grant_attempt' | 'cancel' | 'resume' | 'pause' | 'preflight'
  task_id?: string
  packet_id?: string
  initiative_id?: string
  reason?: string
}

function isSupervisor(value: unknown): value is GatewaySupervisor {
  if (!isRecord(value)) return false
  return (
    typeof value.running === 'boolean'
    && Array.isArray(value.active_runs)
    && typeof value.eligible_now === 'number'
    && typeof value.on_hold === 'number'
    && isNullableString(value.last_tick_at)
    && isRecord(value.budget)
    && typeof value.budget.weekly_budget_cad === 'number'
    && typeof value.budget.estimated_spend_cad === 'number'
    && typeof value.budget.remaining_cad === 'number'
    && typeof value.budget.runs === 'number'
    && typeof value.budget.retries === 'number'
    && typeof value.budget.basis === 'string'
  )
}

export async function fetchSupervisor(): Promise<GatewaySupervisor> {
  const endpoint = `${GATEWAY_BASE}/builder/supervisor`
  const response = await fetch(endpoint)
  if (!response.ok) {
    const detail = await errorDetail(response)
    throw new Error(`GET ${endpoint} failed: ${response.status}${detail ? `: ${detail}` : ''}`)
  }
  const payload: unknown = await response.json()
  if (!isSupervisor(payload)) throw new Error('Gateway /builder/supervisor returned an invalid payload')
  return payload
}

export function useSupervisor() {
  return useQuery({
    queryKey: ['builder-supervisor'],
    queryFn: fetchSupervisor,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

// The command and tick routes answer 200 with {ok:false, error} for refusals
// the operator must see (task not found, initiative already running). Treating
// a non-200 as the only failure would report those refusals as success, so the
// body is the authority and transport failure is folded into the same shape.
async function postCommandResult(endpoint: string, body: unknown): Promise<BuilderCommandResult> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }
  if (isRecord(payload) && typeof payload.ok === 'boolean') {
    return {
      ok: payload.ok,
      action: typeof payload.action === 'string' ? payload.action : undefined,
      error: typeof payload.error === 'string' ? payload.error : null,
      detail: payload.detail,
    }
  }
  if (!response.ok) {
    return { ok: false, error: `Request failed: ${response.status} ${response.statusText}`.trim() }
  }
  return { ok: false, error: 'Builder returned an unreadable response.' }
}

export function runBuilderCommand(command: BuilderCommand): Promise<BuilderCommandResult> {
  return postCommandResult(`${GATEWAY_BASE}/builder/command`, { actor: 'kitty-ui', ...command })
}

export function runSupervisorTick(): Promise<BuilderCommandResult> {
  return postCommandResult(`${GATEWAY_BASE}/builder/supervisor/tick`, {})
}

/** Runs a Builder action and refreshes both projections it can change. */
export function useBuilderAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (command: BuilderCommand | 'tick') =>
      command === 'tick' ? runSupervisorTick() : runBuilderCommand(command),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['work'] })
      void queryClient.invalidateQueries({ queryKey: ['builder-supervisor'] })
    },
  })
}
