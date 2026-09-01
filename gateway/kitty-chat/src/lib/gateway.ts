import { MODELS, type MessageAttachment, type Model } from './types'
import { buildPickerModels, fetchModelPicker } from './model-picker'

const GATEWAY_BASE = '/proxy'
// The proxy has to cross the Next.js boundary and may wake a local gateway
// store on the first request. 2.5s made healthy features look permanently
// offline after a cold start; keep the timeout bounded but realistic.
const DEFAULT_TIMEOUT_MS = 8000
const SEARCH_TIMEOUT_MS = 7000

export interface GatewayHeadline {
  title: string
  url: string
  snippet: string
}

export interface GatewayBrief {
  date: string
  headlines: (string | GatewayHeadline)[]
  memory_snippet: string
  intention: string
  /** 3–5 LLM bullets summarizing today's enriched headlines. Empty when
   *  BRIEF_ENRICH_ARTICLES isn't set. */
  summary_bullets?: string[]
  generated_at: string
  notification_sent: boolean
  error: string | null
}

export interface GatewaySearchHit {
  kind?: 'memory' | 'knowledge' | 'journal' | 'todo' | string
  source: string
  title: string
  text: string
  score: number | null
  metadata?: Record<string, unknown>
}

export interface GatewaySearchSnapshot {
  query: string
  counts: {
    memories: number
    knowledge: number
    journal: number
    todos: number
    inbox: number
  }
  sections: {
    memories: string[]
    knowledge: string[]
    journal: string[]
    todos: string[]
    inbox: string[]
  }
}

// ── Loops ─────────────────────────────────────────────────────────────────────

export type LoopStatus = 'running' | 'paused' | 'error' | 'idle'

export interface GatewayLoop {
  loop_id: string
  name: string
  description?: string
  status: LoopStatus
  interval_minutes?: number
  last_run?: number
  last_result?: string
  error_message?: string
  created_at?: number
  updated_at?: number
}

export interface GatewayLoopsPayload {
  loops: GatewayLoop[]
  fromLiveGateway: boolean
  error: string | null
}

// ── Insights ───────────────────────────────────────────────────────────────────

export type InsightKind = 'pattern' | 'anomaly' | 'suggestion' | 'milestone'

export interface GatewayInsight {
  insight_id: string
  kind: InsightKind
  title: string
  detail?: string
  source?: string
  confidence?: number
  created_at: number
  actions?: Array<{ label: string; action_id: string }>
}

export interface GatewayInsightsPayload {
  insights: GatewayInsight[]
  fromLiveGateway: boolean
  error: string | null
}

/** When `fromLiveGateway` is false, `error` explains why; `data` is still safe to render (fallback or null). */
export type GatewayModelsPayload = {
  models: Model[]
  fromLiveGateway: boolean
  error: string | null
}

export interface GatewayPersonality {
  soul: string
  preferences: string
}

export interface GatewaySessionContext {
  current_branch: string | null
  last_session_topic: string | null
  open_threads: string[]
  next_actions: string[]
}

export interface GatewayUsageSummary {
  totals: { calls: number; tokens: number }
  estimated_cost: { usd: number; cad: number }
  cost_estimate_disclaimer: string
}

export type RuntimeFactState = 'available' | 'unavailable' | 'degraded' | 'stale' | 'unknown'

export interface RuntimeFact<T = unknown> {
  state: RuntimeFactState
  value: T | null
  source: string
  observed_at: string
  valid_until: string
  reason?: string
}

export interface BuilderQueueStatus {
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

export type BuilderFailureKind =
  | 'implementation'
  | 'infrastructure'
  | 'identity'
  | 'scope'
  | 'validation'
  | 'review'
  | 'cancelled'
  | 'blocked'
  | 'exhausted'

export interface BuilderDataQuality {
  state: 'complete' | 'partial'
  issues: string[]
}

export interface BuilderAttemptStatus {
  id: number
  number: number
  outcome: 'succeeded' | 'failed' | 'aborted' | 'crashed' | null
  counts_toward_budget: boolean
  implementation_status: string | null
  validation_status: 'passed' | 'failed' | 'skipped' | null
  review_verdict: 'approve' | 'request_changes' | 'reject' | null
  implementation: {
    status: string | null
    summary: string | null
    diff_summary: string | null
  } | null
  validation: {
    status: 'passed' | 'failed' | 'skipped' | null
    command_count: number
    failed_command_count: number
    summary: string
  } | null
  review: {
    verdict: 'approve' | 'request_changes' | 'reject' | null
    summary: string | null
    findings: Array<{ severity: string | null; note: string | null }>
    findings_truncated: boolean
  } | null
  lease_id: number | null
  created_at: string | null
  updated_at: string | null
  data_quality: BuilderDataQuality
}

export interface BuilderPacketStatus {
  initiative_id: string
  packet_id: string
  title: string
  objective: string | null
  task_id: string
  task_state: string | null
  depends_on: string[]
  eligibility: { state: 'eligible' | 'waiting' | 'blocked' | 'not_queued' | 'unavailable'; blocked_by: string[] }
  budget: { used: number; max: number | null; exhausted: boolean | null }
  attempt_count: number
  attempt_history_truncated: boolean
  attempt_history: BuilderAttemptStatus[]
  lease: { id: number; worker_id: string | null; branch: string | null; base_sha: string | null; created_at: string | null } | null
  run: {
    id: string
    state: string
    started_at: string | null
    last_heartbeat_at: string | null
    ended_at: string | null
    exit_code: number | null
    updated_at: string | null
  } | null
  publication: {
    pr_number: number
    pr_url: string | null
    head_sha: string | null
    checks_state: string | null
    review_state: string | null
    merged: boolean
    merged_at: string | null
    updated_at: string | null
  } | null
  last_event: {
    id: number
    type: string
    created_at: string | null
    reason: string | null
    counts_toward_budget: boolean | null
  } | null
  failure_kind: BuilderFailureKind | null
  blocked_reason: string | null
  last_error: string | null
  updated_at: string | null
  base_sha: string | null
  data_quality: BuilderDataQuality
  investigation: {
    logs: { state: 'unavailable'; reason: string }
    artifacts: { state: 'unavailable'; reason: string }
  }
}

export interface BuilderInitiativeStatus {
  initiative_id: string
  title: string
  state: 'active' | 'paused' | 'completed' | 'failed'
  pause_reason: string | null
  next_packet: string | null
  counts: BuilderQueueStatus & { exhausted: number }
  data_quality: { state: 'complete' | 'partial'; partial_packets: number }
  created_at: string | null
  updated_at: string | null
  packets: BuilderPacketStatus[]
}

export interface BuilderStatusSnapshot {
  schema_version: number
  attempt_history_limit: number
  integrity: {
    state: 'complete' | 'partial'
    partial_packets: number
    total_packets: number
  }
  queue: BuilderQueueStatus
  initiatives: BuilderInitiativeStatus[]
}

export interface GatewayRuntimeManifest {
  schema_version: number
  manifest_id: string
  revision: string
  generated_at: string
  valid_until: string
  application: {
    name: string
    version: RuntimeFact<string>
    build_commit: string | null
    environment: string
  }
  clock: RuntimeFact<{ current_time: string; timezone: string }>
  context: {
    active_project: RuntimeFact<Record<string, unknown>>
    repository: RuntimeFact<{
      root: string
      branch: string
      commit: string
      dirty: boolean
      changed_paths: number
    }>
  }
  execution: {
    builder: RuntimeFact<BuilderStatusSnapshot>
  }
  inference: {
    routing_mode: string
    available_models: RuntimeFact<string[]>
    providers: Array<Record<string, unknown>>
    execution_location: string
  }
  tools: RuntimeFact<Array<Record<string, unknown>>>
  connections: {
    gateway: RuntimeFact<Record<string, unknown>>
    litellm: RuntimeFact<Record<string, unknown>>
  }
  approvals: RuntimeFact<Record<string, unknown>>
}

export type GatewayBriefPayload = {
  brief: GatewayBrief | null
  fromLiveGateway: boolean
  error: string | null
}

export type GatewaySearchPayload = {
  snapshot: GatewaySearchSnapshot | null
  hits: GatewaySearchHit[]
  degradedStores: string[]
  degradedErrors: string[]
  fromLiveGateway: boolean
  error: string | null
}

export type GatewayCapabilityLaunch = 'view' | 'skill'

export interface GatewayCapability {
  id: string
  label: string
  description: string
  category: string
  launch: GatewayCapabilityLaunch
  view?: string
  skill_name?: string
}

export type GatewayCapabilitiesPayload = {
  capabilities: GatewayCapability[]
  fromLiveGateway: boolean
  error: string | null
}

export type GatewayActivityState = 'waiting' | 'running' | 'failed' | 'completed'

export interface GatewayActivityItem {
  id: string
  source: 'action' | 'automation' | 'agent' | 'builder' | string
  source_id: string
  title: string
  detail: string | null
  state: GatewayActivityState
  raw_state: string
  occurred_at: number
  destination: string
}

export interface GatewayActivityProjection {
  items: GatewayActivityItem[]
  counts: { total: number; waiting: number; running: number; failed: number; completed: number }
  sources: Record<string, { state: 'available' | 'unavailable'; reason: string | null }>
}

export interface GatewayWeather {
  temp_c?: number
  feels_like_c?: number
  description?: string
  humidity?: number
  wind_kmph?: number
  max_c?: number
  min_c?: number
  error?: string
}

export type GatewayWeatherPayload = {
  weather: GatewayWeather | null
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

async function fetchWithTimeout(
  input: string,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort()
    } else {
      externalSignal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  try {
    return await fetch(input, { signal: controller.signal })
  } finally {
    window.clearTimeout(timeoutId)
  }
}

const PALETTE = ['#4D9FFF', '#35B7A6', '#E87845', '#B89CFF', '#9BE86B', '#F0D77A']

function hashString(value: string): number {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

function prettyModelName(id: string): string {
  if (!id.startsWith('kitty-')) return id
  return id.slice('kitty-'.length).replace(/-/g, ' ')
}

function colorForModel(id: string): string {
  return PALETTE[hashString(id) % PALETTE.length]
}

function glowForColor(color: string): string {
  return `${color}99`
}

export function buildGatewayModels(ids: string[], displayNames?: Record<string, string>): Model[] {
  const seen = new Set<string>()
  const source = ids.length > 0 ? ids : MODELS.map(model => model.id)
  return source
    .map(id => id.trim())
    .filter(id => id.length > 0)
    .filter(id => {
      if (seen.has(id)) return false
      seen.add(id)
      return true
    })
    .map(id => ({
      id,
      name: displayNames?.[id] ?? prettyModelName(id),
      color: colorForModel(id),
      glow: glowForColor(colorForModel(id)),
    }))
}

export function summarizeGatewaySearch(raw: {
  query?: string
  memories?: GatewaySearchHit[]
  knowledge?: GatewaySearchHit[]
  journal?: GatewaySearchHit[]
  todos?: GatewaySearchHit[]
  inbox?: GatewaySearchHit[]
}): GatewaySearchSnapshot {
  const pick = (items: GatewaySearchHit[] | undefined) =>
    (items ?? []).slice(0, 3).map(item => {
      const title = item.title?.trim()
      const source = item.source?.trim()
      const text = item.text?.trim() ?? ''
      const label = title || source
      return label ? `${label}: ${text}` : text
    }).filter(Boolean)

  const memories = pick(raw.memories)
  const knowledge = pick(raw.knowledge)
  const journal = pick(raw.journal)
  const todos = pick(raw.todos)
  const inbox = pick(raw.inbox)

  return {
    query: (raw.query ?? '').trim(),
    counts: {
      memories: memories.length,
      knowledge: knowledge.length,
      journal: journal.length,
      todos: todos.length,
      inbox: inbox.length,
    },
    sections: {
      memories,
      knowledge,
      journal,
      todos,
      inbox,
    },
  }
}

const fallbackModels = (): Model[] => buildGatewayModels([])

export async function fetchGatewayModels(): Promise<GatewayModelsPayload> {
  try {
    const response = await fetchWithTimeout(`${GATEWAY_BASE}/api/models`)
    if (!response.ok) {
      return {
        models: fallbackModels(),
        fromLiveGateway: false,
        error: describeFetchError(null, response),
      }
    }
    const json = await response.json()
    const displayNames: Record<string, string> = {}
    const ids = Array.isArray(json?.data)
      ? json.data.map((model: { id?: string; display_name?: string }) => {
          if (model?.id && model?.display_name) displayNames[model.id] = model.display_name
          return model?.id
        }).filter((id: unknown): id is string => typeof id === 'string')
      : []
    const liveIds = new Set(ids)
    let picker
    try {
      const controller = new AbortController()
      const timeoutId = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
      try {
        picker = await fetchModelPicker(controller.signal)
      } finally {
        window.clearTimeout(timeoutId)
      }
    } catch (err) {
      const models = MODELS.filter(model => liveIds.has(model.id))
      const error = err instanceof Error && err.name === 'AbortError'
        ? 'Model details timed out — retry to reconnect to Kitty.'
        : `Model details unavailable — ${describeFetchError(err, null)}. Retry to reconnect to Kitty.`
      return {
        models,
        fromLiveGateway: false,
        error,
      }
    }

    const models = buildPickerModels(picker).filter(model => liveIds.has(model.id))
    if (models.length === 0) {
      return {
        models: [],
        fromLiveGateway: false,
        error: 'No live curated models are available — retry to reconnect to Kitty.',
      }
    }
    return {
      models,
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    return {
      models: fallbackModels(),
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

export interface GatewayModelRoute {
  alias: string
  provider: string
  upstream_model: string
  key: { env_var: string | null; present: boolean; note: string | null }
  fallbacks: string[]
}

export interface GatewayModelRouting {
  config_path: string
  readable: boolean
  error: string | null
  routes: GatewayModelRoute[]
  providers: string[]
  warnings: string[]
}

/** Which provider each kitty-* alias actually calls. Throws so the UI can say
 *  "couldn't read the routing" instead of implying everything is fine. */
export async function fetchGatewayModelRouting(): Promise<GatewayModelRouting> {
  return await gfetch<GatewayModelRouting>('/api/model-routing')
}

export interface GatewayProvider {
  name: string
  base_url: string
  model: string | null
  model_env: string | null
  api_key_env: string[]
  requires_key: boolean
  configured: boolean
  disabled: boolean
  position: number | null
  kind: 'local' | 'api_credit' | 'subscription' | string
  free_tier: boolean
}

export interface GatewayProviderChain {
  active: string
  order: string[]
  providers: GatewayProvider[]
  warnings: string[]
  config_path: string
}

export async function fetchGatewayProviders(): Promise<GatewayProviderChain> {
  return await gfetch<GatewayProviderChain>('/api/providers')
}

/** Throws on rejection so a bad order surfaces instead of looking saved. */
export async function saveGatewayProviders(
  order: string[],
  disabled: string[],
  active = 'auto',
): Promise<GatewayProviderChain> {
  return await gfetch<GatewayProviderChain>('/api/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order, disabled, active }),
  })
}

export async function fetchGatewayRuntimeManifest(projectId?: number): Promise<GatewayRuntimeManifest> {
  const suffix = projectId === undefined ? '' : `?project_id=${encodeURIComponent(projectId)}`
  return await gfetch<GatewayRuntimeManifest>(`/runtime/manifest${suffix}`, undefined, 4000)
}

export async function fetchGatewayBrief(): Promise<GatewayBriefPayload> {
  try {
    const response = await fetchWithTimeout(`${GATEWAY_BASE}/brief`, 8000)
    if (!response.ok) {
      return {
        brief: null,
        fromLiveGateway: false,
        error: describeFetchError(null, response),
      }
    }
    const brief = (await response.json()) as GatewayBrief
    return {
      brief,
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    return {
      brief: null,
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

export async function fetchGatewayWeather(): Promise<GatewayWeatherPayload> {
  try {
    const response = await fetchWithTimeout(`${GATEWAY_BASE}/weather`, 1500)
    if (!response.ok) {
      return {
        weather: null,
        fromLiveGateway: false,
        error: describeFetchError(null, response),
      }
    }
    const weather = (await response.json()) as GatewayWeather
    if (weather.error) {
      return {
        weather: null,
        fromLiveGateway: true,
        error: weather.error,
      }
    }
    return {
      weather,
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    return {
      weather: null,
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

// ── Agents ───────────────────────────────────────────────────────────────────

export type AgentStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type AgentType = 'explorer' | 'planner' | 'coder' | 'reviewer' | 'researcher'

export interface AgentSession {
  session_id: number
  goal: string
  status: AgentStatus
  iterations?: number
  total_steps?: number
  last_output_snippet?: string
  created_at?: number
  updated_at?: number
  output?: string
}

export interface AgentWorkspaceAgent {
  id: string
  display_name: string
  role: string
  model: string | null
  status: 'available' | 'paused' | 'retired'
}

export interface AgentWorkspaceMessage {
  id: string
  workspace_id: string
  parent_message_id: string | null
  sender_kind: 'user' | 'agent' | 'system'
  sender_id: string
  recipient_id: string | null
  message_kind: 'prompt' | 'plan' | 'handoff' | 'review' | 'result' | 'status'
  content: string
  created_at: number
}

export interface AgentWorkspaceEvent {
  id: string
  sequence: number
  workspace_id: string
  type: string
  actor_kind: 'user' | 'agent' | 'system'
  actor_id: string
  message_id: string | null
  metadata: Record<string, unknown>
  created_at: number
}

export interface AgentWorkspaceTurn {
  id: string
  workspace_id: string
  user_message_id: string
  status: 'running' | 'completed' | 'failed' | 'interrupted'
  active_agent_id: string | null
  error_type: string | null
  error_message: string | null
  started_at: number
  finished_at: number | null
}

export interface AgentWorkspace {
  id: string
  name: string
  objective: string | null
  status: 'active' | 'paused' | 'closed'
  created_at: number
  updated_at: number
  agents: AgentWorkspaceAgent[]
  messages: AgentWorkspaceMessage[]
  events: AgentWorkspaceEvent[]
  turns: AgentWorkspaceTurn[]
}

async function gfetch<T = unknown>(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${GATEWAY_BASE}${path}`, { ...init, signal: controller.signal })
    if (!response.ok) {
      throw new Error(`Gateway returned ${response.status} ${response.statusText}`.trim())
    }
    return (await response.json()) as T
  } finally {
    window.clearTimeout(timeoutId)
  }
}

// ── Thread goals (per-chat objective, CR-01) ─────────────────────────────────

/** Gateway-enforced objective length cap, mirrored so the editor can stop at
 *  the boundary instead of round-tripping a 400. */
export const OBJECTIVE_MAX_LENGTH = 500

/** Set or clear a chat's thread goal. The gateway returns the updated chat and
 *  omits `objective` when cleared; callers get the server-confirmed value. */
export async function patchChatObjective(
  chatId: string,
  objective: string | null,
): Promise<{ objective: string | null }> {
  const chat = await gfetch<{ objective?: unknown }>(
    `/chats/${encodeURIComponent(chatId)}/objective`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ objective }),
    },
  )
  return { objective: typeof chat.objective === 'string' ? chat.objective : null }
}

// ── Memory correction (CR-06) ────────────────────────────────────────────────

/** Permanently delete a stored memory by id. The gateway 404s when the id is
 *  unknown; callers surface that instead of pretending the forget landed. */
export async function deleteMemory(memoryId: string): Promise<void> {
  await gfetch<{ deleted?: unknown }>(
    `/memories/${encodeURIComponent(memoryId)}`,
    { method: 'DELETE' },
  )
}

export async function fetchGatewayPersonality(): Promise<GatewayPersonality> {
  const payload = await gfetch<unknown>('/settings/personality')
  if (!isRecord(payload) || typeof payload.soul !== 'string' || typeof payload.preferences !== 'string') {
    throw new Error('Gateway /settings/personality returned an invalid payload')
  }
  return payload as unknown as GatewayPersonality
}

export async function updateGatewayPersonality(payload: GatewayPersonality): Promise<void> {
  await gfetch('/settings/personality', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function fetchGatewaySessionContext(): Promise<GatewaySessionContext> {
  const payload = await gfetch<unknown>('/session/context')
  if (!isRecord(payload)) throw new Error('Gateway /session/context returned an invalid payload')
  if (
    (payload.current_branch !== null && typeof payload.current_branch !== 'string')
    || (payload.last_session_topic !== null && typeof payload.last_session_topic !== 'string')
    || !isStringArray(payload.open_threads)
    || !isStringArray(payload.next_actions)
  ) {
    throw new Error('Gateway /session/context returned an invalid payload')
  }
  return payload as unknown as GatewaySessionContext
}

export async function fetchGatewayUsageSummary(): Promise<GatewayUsageSummary> {
  const payload = await gfetch<unknown>('/usage/summary')
  if (!isRecord(payload)) throw new Error('Gateway /usage/summary returned an invalid payload')
  const totals = payload.totals
  const cost = payload.estimated_cost
  if (
    !isRecord(totals)
    || typeof totals.calls !== 'number'
    || typeof totals.tokens !== 'number'
    || !isRecord(cost)
    || typeof cost.usd !== 'number'
    || typeof cost.cad !== 'number'
    || typeof payload.cost_estimate_disclaimer !== 'string'
  ) {
    throw new Error('Gateway /usage/summary returned an invalid payload')
  }
  return payload as unknown as GatewayUsageSummary
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

export async function spawnAgent(goal: string, agentType: AgentType = 'explorer'): Promise<number> {
  const json = await gfetch<{ session_id?: number }>('/agent/spawn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, agent_type: agentType }),
  })
  if (json.session_id === undefined) {
    throw new Error('gateway accepted the agent but returned no session id')
  }
  return json.session_id
}

export async function fetchAgentStatus(sessionId: number): Promise<AgentSession> {
  return await gfetch<AgentSession>(`/agent/${sessionId}`)
}

export async function fetchAgentSessions(limit = 10): Promise<AgentSession[]> {
  const json = await gfetch<{ agents?: AgentSession[] }>(`/agents?limit=${limit}`)
  return json.agents ?? []
}

export async function stopAgent(sessionId: number): Promise<void> {
  await gfetch(`/agent/${sessionId}/stop`, { method: 'POST' })
}

// ── Shared agent workspace ──────────────────────────────────────────────────

export async function createAgentWorkspace(name: string, objective?: string): Promise<AgentWorkspace> {
  return gfetch<AgentWorkspace>('/agent-workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, objective: objective || null }),
  })
}

export async function fetchAgentWorkspace(workspaceId: string): Promise<AgentWorkspace> {
  return gfetch<AgentWorkspace>(`/agent-workspaces/${encodeURIComponent(workspaceId)}`)
}

export async function runAgentWorkspaceTurn(
  workspaceId: string,
  message: string,
): Promise<{ status: 'running'; workspace_id: string; turn: AgentWorkspaceTurn }> {
  return gfetch(`/agent-workspaces/${encodeURIComponent(workspaceId)}/turns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, user_id: 'jacob' }),
  })
}

// ── Todos ────────────────────────────────────────────────────────────────────

export interface GatewayTodo {
  id: number
  content: string
  status: string
  active_form?: string
  sort_order?: number
  created_at?: number
  updated_at?: number
}

export async function fetchGatewayTodos(): Promise<GatewayTodo[]> {
  const json = await gfetch<{ todos?: GatewayTodo[] }>('/todos')
  if (!Array.isArray(json.todos)) {
    throw new Error('Gateway /todos returned an invalid payload: expected a todos array')
  }
  return json.todos
}

export async function addGatewayTodo(content: string): Promise<GatewayTodo> {
  return await gfetch<GatewayTodo>('/todos/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export async function completeGatewayTodo(id: number): Promise<void> {
  await gfetch(`/todos/${id}/complete`, { method: 'POST' })
}

export async function deleteGatewayTodo(id: number): Promise<void> {
  await gfetch(`/todos/${id}`, { method: 'DELETE' })
}

// ── Prompt Templates ─────────────────────────────────────────────────────────

export interface GatewayPromptTemplate {
  id: string | number
  title: string
  content: string
  category?: string
  icon?: string
}

export async function fetchGatewayPrompts(): Promise<GatewayPromptTemplate[]> {
  const json = await gfetch<{ templates?: GatewayPromptTemplate[] }>('/prompts')
  return json.templates ?? []
}

// ── Monitors ─────────────────────────────────────────────────────────────────

export interface GatewayMonitor {
  id: string
  url: string
  label: string
  keywords?: string[]
  interval_minutes?: number
  last_checked?: number | null
  last_hash?: string | null
  last_keyword_matched?: boolean
  enabled?: boolean
}

export async function fetchGatewayMonitors(): Promise<GatewayMonitor[]> {
  const json = await gfetch<{ watches?: GatewayMonitor[] }>('/monitors')
  if (!Array.isArray(json.watches)) {
    throw new Error('Gateway /monitors returned an invalid payload: expected a watches array')
  }
  return json.watches
}

export async function addGatewayMonitor(url: string, label: string): Promise<string> {
  const json = await gfetch<{ watch_id?: string }>('/monitor/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, label }),
  })
  if (!json.watch_id) throw new Error('gateway accepted the monitor but returned no watch id')
  return json.watch_id
}

export async function removeGatewayMonitor(watchId: string): Promise<void> {
  await gfetch(`/monitor/${watchId}`, { method: 'DELETE' })
}

export async function fetchActivity(limit = 40): Promise<GatewayActivityProjection> {
  return await gfetch<GatewayActivityProjection>(`/activity?limit=${limit}`)
}

export async function fetchCapabilities(): Promise<GatewayCapabilitiesPayload> {
  try {
    const json = await gfetch<{ capabilities?: GatewayCapability[] }>('/capabilities')
    if (!Array.isArray(json.capabilities)) {
      throw new Error('Gateway /capabilities returned an invalid payload')
    }
    const capabilities = json.capabilities.filter((item) => (
      item
      && typeof item.id === 'string'
      && typeof item.label === 'string'
      && typeof item.description === 'string'
      && typeof item.category === 'string'
      && (item.launch === 'view' || item.launch === 'skill')
    ))
    return { capabilities, fromLiveGateway: true, error: null }
  } catch (err) {
    return { capabilities: [], fromLiveGateway: false, error: describeFetchError(err, null) }
  }
}

export async function fetchGatewaySearch(
  query: string,
  limit = 5,
  signal?: AbortSignal,
): Promise<GatewaySearchPayload> {
  const q = query.trim()
  if (!q) {
    return { snapshot: null, hits: [], degradedStores: [], degradedErrors: [], fromLiveGateway: true, error: null }
  }

  try {
    const response = await fetchWithTimeout(
      `${GATEWAY_BASE}/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      SEARCH_TIMEOUT_MS,
      signal,
    )
    if (!response.ok) {
      return {
        snapshot: null,
        hits: [],
        degradedStores: [],
        degradedErrors: [],
        fromLiveGateway: false,
        error: describeFetchError(null, response),
      }
    }
    const json = await response.json()
    const grouped: Record<string, GatewaySearchHit[]> = {
      memory: [],
      knowledge: [],
      journal: [],
      todos: [],
      inbox: [],
    }
    const hits: GatewaySearchHit[] = []
    const degradedStores = Array.isArray(json?.degraded_stores)
      ? json.degraded_stores
        .filter((store: unknown): store is string => typeof store === 'string' && store.length > 0)
        .slice(0, 10)
        .map((store: string) => store.slice(0, 64))
      : []
    const degradedErrors = Array.isArray(json?.errors)
      ? json.errors
        .filter((error: unknown): error is string => typeof error === 'string')
        .slice(0, 5)
        .map((error: string) => error.slice(0, 240))
      : []
    for (const row of Array.isArray(json?.results) ? json.results : []) {
      const store = typeof row?.store === 'string' ? row.store : ''
      if (!(store in grouped) || typeof row?.content !== 'string') continue
      const hit: GatewaySearchHit = {
        kind: typeof row.kind === 'string' ? row.kind : store,
        source: typeof row.source === 'string' ? row.source : store,
        title: typeof row.title === 'string' ? row.title : store,
        text: row.content,
        score: typeof row.score === 'number' ? row.score : null,
        metadata: isRecord(row.metadata) ? row.metadata : undefined,
      }
      grouped[store].push(hit)
      hits.push(hit)
    }
    return {
      snapshot: summarizeGatewaySearch({
        query: q,
        memories: grouped.memory,
        knowledge: grouped.knowledge,
        journal: grouped.journal,
        todos: grouped.todos,
        inbox: grouped.inbox,
      }),
      hits,
      degradedStores,
      degradedErrors,
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      if (signal?.aborted) {
        return { snapshot: null, hits: [], degradedStores: [], degradedErrors: [], fromLiveGateway: true, error: null }
      }
      return {
        snapshot: null,
        hits: [],
        degradedStores: [],
        degradedErrors: [],
        fromLiveGateway: false,
        error: 'Request timed out — is the Kitty gateway running?',
      }
    }
    return {
      snapshot: null,
      hits: [],
      degradedStores: [],
      degradedErrors: [],
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

// ── Loops Fetch ───────────────────────────────────────────────────────────────

export async function fetchGatewayLoops(): Promise<GatewayLoopsPayload> {
  try {
    const json = await gfetch<{ loops?: GatewayLoop[] }>('/loops')
    return {
      loops: json.loops ?? [],
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    return {
      loops: [],
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

export async function toggleGatewayLoop(loopId: string): Promise<void> {
  await gfetch(`/loop/${loopId}/toggle`, { method: 'POST' })
}

// ── Insights Fetch ────────────────────────────────────────────────────────────

export async function fetchGatewayInsights(limit = 10): Promise<GatewayInsightsPayload> {
  try {
    const json = await gfetch<{ insights?: GatewayInsight[] }>(`/insights?limit=${limit}`)
    return {
      insights: json.insights ?? [],
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    return {
      insights: [],
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

export async function dismissGatewayInsight(insightId: string): Promise<void> {
  await gfetch(`/insight/${insightId}/dismiss`, { method: 'POST' })
}

// ── Cron Schedules ────────────────────────────────────────────────────────────

export type CronScheduleType = 'daily' | 'interval' | 'once'

export interface CronSchedule {
  id: string
  name: string
  action: string
  schedule_type: CronScheduleType
  schedule_value: string
  last_run: number
  enabled: number
}

export async function fetchCronSchedules(): Promise<CronSchedule[]> {
  const json = await gfetch<{ schedules?: CronSchedule[] }>('/cron/schedules')
  return json.schedules ?? []
}

export async function fetchCronActions(): Promise<string[]> {
  const json = await gfetch<{ actions?: string[] }>('/cron/actions')
  return json.actions ?? []
}

export async function createCronSchedule(
  name: string,
  action: string,
  scheduleType: CronScheduleType,
  scheduleValue: string,
): Promise<string> {
  const json = await gfetch<{ id?: string }>('/cron/schedule', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, action, schedule_type: scheduleType, schedule_value: scheduleValue }),
  })
  if (!json.id) throw new Error('gateway accepted the schedule but returned no id')
  return json.id
}

export async function deleteCronSchedule(id: string): Promise<void> {
  await gfetch(`/cron/schedule/${id}`, { method: 'DELETE' })
}

export async function updateCronSchedule(
  id: string,
  name: string,
  action: string,
  scheduleType: CronScheduleType,
  scheduleValue: string,
): Promise<void> {
  await gfetch(`/cron/schedule/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, action, schedule_type: scheduleType, schedule_value: scheduleValue }),
  })
}

export async function toggleCronSchedule(id: string): Promise<void> {
  await gfetch(`/cron/schedule/${id}/toggle`, { method: 'POST' })
}

export interface AutomationRetryResult {
  run: { id: string; status: string }
  retried_from: string
}

export async function retryAutomationRun(runId: string): Promise<AutomationRetryResult> {
  return gfetch<AutomationRetryResult>(`/automations/runs/${encodeURIComponent(runId)}/retry`, {
    method: 'POST',
  })
}

// ── Why didn't this happen? ─────────────────────────────────────────────────

export type WhyStatus =
  | 'not_yet_due'
  | 'disabled'
  | 'already_claimed'
  | 'claimed'
  | 'source_unavailable'
  | 'condition_false'
  | 'policy_refused'
  | 'approval_required'
  | 'grant_expired'
  | 'grant_revoked'
  | 'action_unavailable'
  | 'failed'
  | 'interrupted'
  | 'completed'
  | 'execution_gap'
  | 'pending_claim'
  | 'not_triggered'

export interface WhyExplanation {
  status: WhyStatus
  reason: string
  relevant_at: number | null
  action: string
  automation: string
  evidence: Record<string, unknown>
  next_step: string
}

export async function fetchScheduleWhy(scheduleId: string): Promise<WhyExplanation> {
  const json = await gfetch<{ explanation?: WhyExplanation }>(
    `/automations/schedules/${scheduleId}/why`,
  )
  if (!json.explanation) throw new Error(`gateway returned no explanation for schedule ${scheduleId}`)
  return json.explanation
}

export async function fetchActionWhy(action: string): Promise<WhyExplanation> {
  const json = await gfetch<{ explanation?: WhyExplanation }>(
    `/automations/${encodeURIComponent(action)}/why`,
  )
  if (!json.explanation) throw new Error(`gateway returned no explanation for action ${action}`)
  return json.explanation
}

// ── Dream / Performance ─────────────────────────────────────────────────────

export interface DreamStatusPayload {
  status: string
  last_run: number | null
  last_run_label?: string | null
  next_run?: number | null
  insights_count: number
  never: boolean
}

export async function fetchDreamStatus(): Promise<DreamStatusPayload> {
  return await gfetch<DreamStatusPayload>('/dream/status')
}

export async function triggerDreamConsolidation(): Promise<boolean> {
  await gfetch('/dream/trigger', { method: 'POST' })
  return true
}

export interface PerfStats {
  window_hours: number
  total_requests: number
  avg_latency_ms: number
  max_latency_ms: number
  min_latency_ms: number
  total_tokens: number
  avg_tokens: number
  active_schedules: number
  schedules: CronSchedule[]
}

export async function fetchPerfStats(windowHours = 24): Promise<PerfStats> {
  return await gfetch<PerfStats>(`/perf/stats?window_hours=${windowHours}`)
}

// ── Image Generation ──────────────────────────────────────────────────────────

export interface ImageEntry {
  prompt_id: string
  /** Durable IMG-01 job id — stable across gateway restarts. */
  job_id?: string
  filename: string
  prompt: string
  created_at?: number | string
}

export interface ImageEngineStatus {
  name: string
  label: string
  available: boolean
  unavailable_reason?: string | null
}

export interface ImageStatus {
  available: boolean
  backend?: string
  engines?: ImageEngineStatus[]
}

export async function fetchImageStatus(): Promise<ImageStatus> {
  // Deliberately no catch: a reachable gateway with offline renderers answers
  // { available: false }, while an unreachable gateway/proxy throws. Swallowing
  // every failure into "offline renderers" hides a down Gateway behind the
  // "start ComfyUI" recovery, which sends the user down the wrong path.
  const json = await gfetch<{
    available?: boolean
    backend?: string
    engines?: ImageEngineStatus[]
  }>('/image/status')
  return {
    available: json.available === true,
    backend: json.backend,
    engines: json.engines ?? [],
  }
}

export async function generateImage(
  prompt: string,
  engine = 'comfyui',
): Promise<{ filename: string; job_id?: string; engine?: string }> {
  return await gfetch<{ filename: string; job_id?: string; engine?: string }>('/image/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, engine }),
  })
}

export async function fetchImageHistory(limit = 20): Promise<ImageEntry[]> {
  const json = await gfetch<{ images?: ImageEntry[] }>(`/image/history?limit=${limit}`)
  return json.images ?? []
}

// ── State / Actions ──────────────────────────────────────────────────────────

export interface StateChange {
  section: string
  field: string
  before: unknown
  after: unknown
}

export interface StateChangesPayload {
  baseline_ts: number | null
  current_ts: number
  changes: StateChange[]
  new_signals: Array<Record<string, unknown>>
  note?: string
}

export interface GatewayAction {
  id: number
  created_at: string
  source_kind: string
  source_id: string | null
  kind: string
  title: string
  preview: string
  payload: Record<string, unknown>
  risk_tier: 'T0' | 'T1' | 'T2'
  status: string
  result: string | null
  decided_at: number | null
  executed_at: number | null
}

export async function fetchStateChanges(): Promise<StateChangesPayload> {
  return gfetch<StateChangesPayload>('/state/changes')
}

export async function fetchActions(status?: string): Promise<GatewayAction[]> {
  const url = status ? `/actions?status=${status}` : '/actions'
  const json = await gfetch<{ actions: GatewayAction[] }>(url)
  return json.actions ?? []
}

export async function fetchAction(id: number): Promise<GatewayAction> {
  return gfetch<GatewayAction>(`/actions/${id}`)
}

export async function approveAction(id: number): Promise<GatewayAction> {
  return gfetch<GatewayAction>(`/actions/${id}/approve`, { method: 'POST' })
}

export async function rejectAction(id: number): Promise<void> {
  await gfetch(`/actions/${id}/reject`, { method: 'POST' })
}

/** Dispatch an approved (or auto-executable) action through its executor.
 *  Approving a T2 action does not run it — this is the second, separate
 *  call that actually produces the durable result. */
export async function executeAction(id: number): Promise<GatewayAction> {
  return gfetch<GatewayAction>(`/actions/${id}/execute`, { method: 'POST' })
}

export async function snapshotState(): Promise<void> {
  await gfetch('/state/snapshot', { method: 'POST' })
}

export interface GatewayStateSection {
  ok: boolean
  error?: string
  [key: string]: unknown
}

export interface GatewayStateNow {
  ts: number
  sections: Record<string, GatewayStateSection>
}

export async function fetchStateNow(): Promise<GatewayStateNow> {
  return gfetch<GatewayStateNow>('/state/now')
}

export async function runInboxTriage(limit = 25): Promise<void> {
  await gfetch(`/inbox/triage?limit=${limit}`, { method: 'POST' })
}

// ── Inbox triage (needs_jacob bucket) ────────────────────────────────────────

export interface GatewayTriageEntry {
  inbox_id: string
  ts: number
  bucket: string
  confidence: number
  rationale: string
  model?: string
  text: string | null
  created_at: string | null
}

export interface GatewayNeedsJacobPayload {
  entries: GatewayTriageEntry[]
  fromLiveGateway: boolean
  error: string | null
}

export async function fetchNeedsJacob(limit = 20): Promise<GatewayNeedsJacobPayload> {
  try {
    const json = await gfetch<{ entries?: GatewayTriageEntry[] }>(
      `/inbox/triaged?bucket=needs_jacob&limit=${limit}`,
    )
    return {
      entries: json.entries ?? [],
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    return {
      entries: [],
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}

// ── File Capture ─────────────────────────────────────────────────────────────

export interface CaptureResult {
  capture_id: string
  artifact_id?: string | null
  status: string
  message: string
}

export async function uploadCaptureFile(
  file: File,
  opts?: { conversationId?: string; projectId?: number },
): Promise<CaptureResult> {
  const formData = new FormData()
  formData.append('file', file)
  if (opts?.conversationId) formData.append('conversation_id', opts.conversationId)
  if (opts?.projectId !== undefined) formData.append('project_id', String(opts.projectId))
  return await gfetch<CaptureResult>('/capture/file', {
    method: 'POST',
    body: formData,
  })
}

// ── Projects ─────────────────────────────────────────────────────────────────

export interface GatewayProject {
  id: number
  name: string
  kind: string
  status: string
  summary: string | null
  paths: string[]
  last_touched: number | null
  open_questions: string[]
  next_actions: string[]
  links: unknown[]
}

export interface GatewayActiveProjectPayload {
  project_id: number
  project: GatewayProject
  source: 'persisted' | 'defaulted_once' | string
}

export interface GatewayNextStep {
  project_id: number
  step: string
  why: string
  recent_win: string
  delegable: boolean
  generated_at: number
}

/** The bounded artifact slice project_resume.resume() projects — see gateway/project_resume.py. */
export interface GatewayProjectArtifact {
  id: string
  kind: string
  display_name: string
  state: string
  created_at: number
  media_type: string
  size_bytes: number
}

/** One Builder initiative projected as a Work item — see gateway/_work_projection_item.py. */
export interface GatewayProjectWorkItem {
  id: string
  title: string | null
  state: 'active' | 'blocked' | 'failed' | 'ready' | 'waiting' | 'paused' | 'completed'
  next_action: string | null
  updated_at: string | null
}

/** The Work snapshot project_resume.resume() scopes to this project — see gateway/project_resume.py. */
export interface GatewayProjectWork {
  items: GatewayProjectWorkItem[]
  total_items: number
}

export interface GatewayProjectConversation {
  id: string
  title: string
  objective: string | null
  updated_at: number
}

export interface GatewayProjectDeadline {
  id: number
  due_date: string
  obligation: string
  amount: string | null
  currency: string | null
  confidence: string
  status: string
}

export interface GatewayProjectSection<T> {
  items: T[]
  error: string | null
}

export interface GatewayProjectResume {
  id: number
  artifacts: GatewayProjectArtifact[]
  work: GatewayProjectWork
  conversations: GatewayProjectSection<GatewayProjectConversation>
  deadlines: GatewayProjectSection<GatewayProjectDeadline>
}

export function artifactContentUrl(artifactId: string): string {
  return `${GATEWAY_BASE}/artifacts/${encodeURIComponent(artifactId)}/content`
}

export async function fetchArtifactText(artifactId: string): Promise<string> {
  const response = await fetch(artifactContentUrl(artifactId))
  if (!response.ok) {
    throw new Error(`Gateway returned ${response.status} ${response.statusText}`.trim())
  }
  return await response.text()
}

export interface GatewayArtifact {
  id: string
  project_id: number | null
  kind: string
  media_type: string
  display_name: string
  state: string
  storage_uri?: string
  content_hash?: string
  size_bytes: number
  created_at: number
  created_by: string
  source_ref?: string | null
  conversation_id?: string | null
  work_item_id?: string | null
  run_id?: string | null
  metadata: Record<string, unknown>
  error?: string | null
}

/** Metadata for a Library image staged into the Chat composer. The Gateway
 *  resolves the durable artifact bytes only when the message is sent. */
export type ChatImageAttachment = MessageAttachment

/** The route already writes its rejection reasons for a person to read, so the
 *  render boundary shows `detail` verbatim rather than collapsing every 4xx
 *  into one generic sentence. Anything without a reason keeps the raw
 *  diagnostic form for `describeFailure` to translate. */
async function artifactChatRejection(response: Response): Promise<Error | null> {
  let detail: unknown
  try {
    const body: unknown = await response.json()
    detail = body && typeof body === 'object' ? (body as { detail?: unknown }).detail : null
  } catch {
    return null
  }
  if (typeof detail !== 'string' || detail.trim() === '') return null
  const rejection = new Error(detail.slice(0, 300))
  rejection.name = 'ArtifactChatRejection'
  return rejection
}

/** Resolve a saved artifact for use in chat. Throws on rejection so the UI
 *  can show the gateway's plain-language reason instead of a fake success. */
export async function useArtifactInChat(artifactId: string): Promise<ChatImageAttachment> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
  try {
    const response = await fetch(`${GATEWAY_BASE}/chats/use-in-chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact_id: artifactId }),
      signal: controller.signal,
    })
    if (!response.ok) {
      throw (await artifactChatRejection(response))
        ?? new Error(`Gateway returned ${response.status} ${response.statusText}`.trim())
    }
    return (await response.json()) as ChatImageAttachment
  } finally {
    window.clearTimeout(timeoutId)
  }
}

// Projects/knowledge/provider fetchers throw on failure — react-query's
// isError is the honest signal, not a silently empty list.
export async function fetchProjects(): Promise<GatewayProject[]> {
  const json = await gfetch<{ projects?: GatewayProject[] }>('/projects')
  return json.projects ?? []
}

export async function fetchArtifacts(limit = 100): Promise<GatewayArtifact[]> {
  const json = await gfetch<unknown>(`/artifacts?limit=${limit}`)
  if (!isRecord(json) || !Array.isArray(json.artifacts)) {
    throw new Error('Saved files returned an invalid response')
  }

  return json.artifacts.map(normalizeGatewayArtifact)
}

export async function fetchArtifact(artifactId: string): Promise<GatewayArtifact> {
  const json = await gfetch<unknown>(`/artifacts/${encodeURIComponent(artifactId)}`)
  return normalizeGatewayArtifact(json)
}

function normalizeGatewayArtifact(item: unknown): GatewayArtifact {
  if (
    !isRecord(item)
    || typeof item.id !== 'string'
    || (item.project_id !== null && typeof item.project_id !== 'number')
    || typeof item.kind !== 'string'
    || typeof item.media_type !== 'string'
    || typeof item.display_name !== 'string'
    || typeof item.state !== 'string'
    || typeof item.size_bytes !== 'number'
    || typeof item.created_at !== 'number'
    || typeof item.created_by !== 'string'
  ) {
    throw new Error('Saved files returned an invalid response')
  }
  return {
    ...item,
    metadata: isRecord(item.metadata) ? item.metadata : {},
  } as GatewayArtifact
}

export async function fetchActiveProject(): Promise<GatewayActiveProjectPayload> {
  return await gfetch<GatewayActiveProjectPayload>('/context/project')
}

export async function setActiveProject(projectId: number): Promise<GatewayActiveProjectPayload> {
  return await gfetch<GatewayActiveProjectPayload>('/context/project', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  })
}

/** null means "no step generated yet" (gateway 404s rather than fabricating one). */
export async function fetchProjectNext(projectId: number): Promise<GatewayNextStep | null> {
  try {
    return await gfetch<GatewayNextStep>(`/projects/${projectId}/next`)
  } catch (err) {
    if (err instanceof Error && err.message.includes('404')) return null
    throw err
  }
}

export async function fetchProjectNextSteps(limit = 3): Promise<GatewayNextStep[]> {
  return await gfetch<GatewayNextStep[]>(`/projects/next-steps?limit=${limit}`)
}

export async function fetchProjectNextStepMap(projectIds: number[]): Promise<GatewayNextStep[]> {
  if (projectIds.length === 0) return []
  const encoded = encodeURIComponent(projectIds.join(','))
  return await gfetch<GatewayNextStep[]>(`/projects/next-step-map?project_ids=${encoded}`)
}

export async function fetchProjectResume(projectId: number): Promise<GatewayProjectResume> {
  return await gfetch<GatewayProjectResume>(`/projects/${projectId}/resume`)
}

/** Blocks on git + LLM composition server-side — give it a long timeout. */
export async function refreshProject(projectId: number): Promise<{ next_step?: { ok: boolean; step?: string; error?: string } }> {
  return await gfetch(`/projects/${projectId}/refresh`, { method: 'POST' }, 60_000)
}

// ── Deadlines (urgent paper, docs/packets/017) ───────────────────────────────

export interface GatewayDeadline {
  id: number
  project_id: number
  source: string
  source_id: string | null
  due_date: string
  obligation: string
  amount: number | null
  currency: string | null
  confidence: 'high' | 'medium' | 'low' | 'needs_jacob'
  status: 'open' | 'closed' | 'needs_jacob'
  dedupe_key: string
  created_at: number
  updated_at: number
  pushed_at: number | null
}

export interface GatewayDeadlinesPayload {
  deadlines: GatewayDeadline[]
  fromLiveGateway: boolean
  error: string | null
}

/** Backend returns rows already sorted by due_date ASC, so `deadlines[0]` is the
 *  nearest due item. Transport errors fold into `fromLiveGateway:false` so the
 *  Home card can tell "gateway down" apart from "nothing tracked". */
export async function fetchDeadlines(status = 'open'): Promise<GatewayDeadlinesPayload> {
  try {
    const json = await gfetch<{ deadlines?: GatewayDeadline[] }>(
      `/deadlines?status=${encodeURIComponent(status)}`,
    )
    return { deadlines: json.deadlines ?? [], fromLiveGateway: true, error: null }
  } catch (err) {
    return { deadlines: [], fromLiveGateway: false, error: describeFetchError(err, null) }
  }
}

export interface DeadlineSweepReport {
  found: number
  open: number
  needs_jacob: number
  top: GatewayDeadline | null
  blind_spots: string[]
  generated_at: string
  escalated: number
  escalation_failed: number
  delivery_status: 'delivered' | 'partial' | 'source_unavailable' | 'nothing_due' | 'not_requested'
  delivery_message: string
}

/** The sweep scans documents + mail via the LLM server-side — give it room. */
export async function runDeadlineSweep(): Promise<DeadlineSweepReport> {
  return await gfetch<DeadlineSweepReport>('/deadlines/sweep', { method: 'POST' }, 60_000)
}

// ── Knowledge (Documents) ────────────────────────────────────────────────────

export interface KnowledgeSource {
  name: string
  chunks: number
  collection: string
  tags: string[]
  doc_types: string[]
  sensitivities: string[]
  primary_topic?: string | null
  file_path?: string | null
  ingested_at?: number | null
}

export interface KnowledgeSourcesPayload {
  sources: KnowledgeSource[]
  total_sources: number
  total_chunks: number
}

export interface KnowledgeSearchResult {
  text: string
  source: string
  doc_type: string
  score: number | null
  reference: { source: string; chunk_index?: number | null; page_num?: number | null }
}

export interface KnowledgeSearchPayload {
  query: string
  results: KnowledgeSearchResult[]
  message?: string
  count?: number
}

export interface KnowledgeIngestResult {
  status: 'success' | 'skipped' | 'failed' | 'pending'
  source_id: string
  reason: string
}

// ── Tutor (DTH-03/04 wiring) ─────────────────────────────────────────────────

export interface TutorQuizQuestion {
  question: string
  options: string[]
  answer_label: string
}

export interface TutorQuizPayload {
  questions: TutorQuizQuestion[]
  due: number
}

export interface TutorAttemptResult {
  term: string
  mastery: number
  stage: 'new' | 'learning' | 'mastered'
  next_action: string
}

export interface TutorAnswer {
  vocab: string[]
  explain: string
  question: string
}

export async function fetchTutorQuiz(limit = 5): Promise<TutorQuizPayload> {
  return await gfetch<TutorQuizPayload>(`/tutor/quiz?limit=${limit}`, undefined, 10_000)
}

export async function postTutorAttempt(
  term: string,
  correct: boolean,
  kpType = 'memory',
): Promise<TutorAttemptResult> {
  return await gfetch<TutorAttemptResult>('/tutor/attempt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ term, correct, kp_type: kpType }),
  })
}

export async function askTutor(topic: string): Promise<TutorAnswer> {
  return await gfetch<TutorAnswer>('/tutor/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  }, 60_000)
}

export interface TutorLearnResult {
  ingested: number
  status: string
  label?: string
}

export interface TutorReviewItem {
  term: string
  knowledge_type: string
  confidence: number
  stage: string
  last_seen: string
}

export interface TutorTermMastery {
  term: string
  mastery: number
  stage: string
  next_action: string
}

export async function tutorLearn(path: string, label?: string): Promise<TutorLearnResult> {
  return await gfetch<TutorLearnResult>('/tutor/learn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, ...(label ? { label } : {}) }),
  }, 120_000)
}

export async function fetchTutorReview(): Promise<{ due: TutorReviewItem[] }> {
  return await gfetch<{ due: TutorReviewItem[] }>('/tutor/review', undefined, 10_000)
}

export async function postTutorGrade(term: string, answer: string, kpType = 'memory'): Promise<{ correct: boolean }> {
  return await gfetch<{ correct: boolean }>('/tutor/grade', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ term, answer, kp_type: kpType }),
  })
}

export async function fetchTutorTerm(term: string, kpType = 'memory'): Promise<TutorTermMastery> {
  return await gfetch<TutorTermMastery>(
    `/tutor/term/${encodeURIComponent(term)}?kp_type=${kpType}`,
    undefined,
    10_000,
  )
}

export async function fetchKnowledgeSources(): Promise<KnowledgeSourcesPayload> {
  return await gfetch<KnowledgeSourcesPayload>('/knowledge/sources', undefined, 10_000)
}

export async function searchKnowledge(q: string, limit = 8): Promise<KnowledgeSearchPayload> {
  return await gfetch<KnowledgeSearchPayload>(
    `/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    undefined,
    15_000,
  )
}

/** Ingest a Mac file path or a URL. The gateway downloads/parses/indexes and
 *  answers with an explicit status + reason — surface both verbatim. */
export async function ingestKnowledge(body: {
  path?: string
  url?: string
  collection?: string
  tags?: string[]
}): Promise<KnowledgeIngestResult> {
  return await gfetch<KnowledgeIngestResult>(
    '/knowledge/ingest',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    120_000,
  )
}

// ── Providers (plugins + MCP) ────────────────────────────────────────────────

export interface GatewayPlugin {
  name: string
  description?: string
  enabled: boolean
  version?: string
}

export interface McpServer {
  name: string
  status?: string
  transport?: string
  tools?: number
  [key: string]: unknown
}

export interface McpTool {
  name: string
  description?: string
  [key: string]: unknown
}

export async function fetchPlugins(): Promise<GatewayPlugin[]> {
  const json = await gfetch<{ plugins?: GatewayPlugin[] }>('/plugins')
  return json.plugins ?? []
}

export async function setPluginEnabled(name: string, enabled: boolean): Promise<void> {
  await gfetch(`/plugin/${encodeURIComponent(name)}/${enabled ? 'enable' : 'disable'}`, {
    method: 'POST',
  })
}

export async function fetchMcpServers(): Promise<McpServer[]> {
  const json = await gfetch<{ servers?: McpServer[] }>('/mcp/servers')
  return json.servers ?? []
}

export async function fetchMcpTools(): Promise<McpTool[]> {
  const json = await gfetch<{ tools?: McpTool[] }>('/mcp/tools')
  return json.tools ?? []
}

// ── Cockpit health signals ───────────────────────────────────────────────────

export interface GatewayHealthPayload {
  ok: boolean
  /** Direct probe from the gateway's /health — the honest LiteLLM signal
   *  (/api/models masks proxy failures behind a fallback model list). */
  litellmReachable: boolean
  error: string | null
}

export async function fetchGatewayHealth(): Promise<GatewayHealthPayload> {
  try {
    const json = await gfetch<{ status?: string; litellm_reachable?: boolean }>(
      '/health',
      undefined,
      4000,
    )
    return json.status === 'ok'
      ? { ok: true, litellmReachable: json.litellm_reachable === true, error: null }
      : {
          ok: false,
          litellmReachable: false,
          error: `unexpected /health payload: ${JSON.stringify(json)}`,
        }
  } catch (err) {
    return { ok: false, litellmReachable: false, error: describeFetchError(err, null) }
  }
}

export type HealthDomainState = 'available' | 'degraded' | 'stale' | 'unavailable' | 'unknown'

export interface HealthDomainStatus {
  name: string
  status: HealthDomainState
  reason: string
  detail: Record<string, unknown>
}

export type HealthSurfaceOverall = 'healthy' | 'degraded' | 'unavailable'

export interface HealthSurfacePayload {
  ok: boolean
  generated_at: string | null
  overall: HealthSurfaceOverall | null
  domains: HealthDomainStatus[]
  degraded: string[]
  still_functional: string[]
  pending_grants: number
  error?: string
}

/** Full-stack health projection from /health/surface — the single surface
 *  answering "is Kitty working, and if not, exactly what is wrong?". */
export async function fetchHealthSurface(): Promise<HealthSurfacePayload> {
  try {
    const json = await gfetch<{
      generated_at?: string
      overall?: HealthSurfaceOverall
      domains?: HealthDomainStatus[]
      degraded?: string[]
      still_functional?: string[]
      pending_grants?: number
    }>('/health/surface', undefined, 4000)
    return {
      ok: true,
      generated_at: json.generated_at ?? null,
      overall: json.overall ?? null,
      domains: Array.isArray(json.domains) ? json.domains : [],
      degraded: Array.isArray(json.degraded) ? json.degraded : [],
      still_functional: Array.isArray(json.still_functional) ? json.still_functional : [],
      pending_grants: typeof json.pending_grants === 'number' ? json.pending_grants : 0,
    }
  } catch (err) {
    return {
      ok: false,
      generated_at: null,
      overall: null,
      domains: [],
      degraded: [],
      still_functional: [],
      pending_grants: 0,
      error: describeFetchError(err, null),
    }
  }
}

export interface GatewayTailnetPayload {
  ok: boolean
  tailnetIp: string | null
  uiUrl: string | null
}

export async function fetchGatewayTailnet(): Promise<GatewayTailnetPayload> {
  try {
    const json = await gfetch<{ ok?: boolean; tailnet_ip?: string | null; ui_url?: string | null }>(
      '/network/tailnet',
      undefined,
      1500,
    )
    return { ok: json.ok === true, tailnetIp: json.tailnet_ip ?? null, uiUrl: json.ui_url ?? null }
  } catch {
    return { ok: false, tailnetIp: null, uiUrl: null }
  }
}

export interface ChatsPersistencePayload {
  ok: boolean
  count: number
  error: string | null
}

/** Chat persistence health = the actual chats table answering. */
export async function fetchChatsPersistence(): Promise<ChatsPersistencePayload> {
  try {
    const json = await gfetch<{ chats?: unknown[] }>('/chats', undefined, 6000)
    if (!Array.isArray(json.chats)) {
      return { ok: false, count: 0, error: '/chats answered without a chats array' }
    }
    return { ok: true, count: json.chats.length, error: null }
  } catch (err) {
    return { ok: false, count: 0, error: describeFetchError(err, null) }
  }
}


// ── Logs ──────────────────────────────────────────────────────────────────────

export interface LogTailPayload {
  file: string
  lines: string[]
}

export async function fetchLogTail(file = 'gateway', lines = 100): Promise<LogTailPayload> {
  return await gfetch<LogTailPayload>(`/logs/tail?file=${encodeURIComponent(file)}&lines=${lines}`)
}

// ── Repairs ────────────────────────────────────────────────────────────────────

export interface RepairItem {
  id: string
  severity: 'ok' | 'warn' | 'error'
  title: string
  detail: string
  fix?: {
    label: string
    action_kind: string
    check_name: string
  } | null
}

export interface RepairsPayload {
  ok: boolean
  checks_run: number
  issues: number
  repairs: RepairItem[]
  error?: string
}

export async function fetchRepairs(): Promise<RepairsPayload> {
  try {
    return await gfetch<RepairsPayload>('/repairs', undefined, 8000)
  } catch (err) {
    return { ok: false, checks_run: 0, issues: 0, repairs: [], error: describeFetchError(err, null) }
  }
}

export async function executeRepair(repairId: string, actionKind: string, checkName: string) {
  const endpoint = actionKind === 'repair.dismiss' ? '/repairs/dismiss' : '/repairs/check'
  return await gfetch<{ ok: boolean; action_id?: number; error?: string }>(
    endpoint,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repair_id: repairId, check_name: checkName }),
    },
    8000,
  )
}

// ── Builder operator commands (KB-BRAIN-05) ───────────────────────────────────

export interface OperatorCommandPayload {
  action: string
  task_id?: string
  initiative_id?: string
  packet_id?: string
  reason?: string
  actor?: string
  expected_version?: number
}

export interface OperatorCommandResult {
  ok: boolean
  action?: string
  task_id?: string
  error?: string
  detail?: string
  event_id?: number
  evidence?: Record<string, unknown>
  available?: string[]
}

export async function executeOperatorCommand(payload: OperatorCommandPayload): Promise<OperatorCommandResult> {
  return await gfetch<OperatorCommandResult>(
    '/builder/command',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    15000,
  )
}

// ── Conversation -> Builder job handoff ───────────────────────────────────────
// Mirrors the KittyBuilder MCP bridge's propose/approve contract (see
// gateway/conversation_handoff.py) so a job proposed from a Kitty chat and one
// proposed by an MCP client share one approval mechanism and one durable store.

export interface ConversationProposeRequest {
  objective: string
  instructions: string
  allowed_paths: string[]
  initiative_id?: string
  title?: string
  acceptance_criteria?: string[]
  validation_commands?: string[]
}

export interface ConversationProposal {
  ok: boolean
  state?: string | null
  error_code?: string | null
  error?: string | null
  next_action?: string | null
  mission_id?: string | null
  manifest_sha256?: string
  expected_base_sha?: string
  approval_nonce?: string
  warnings?: string[]
  prepared_manifest?: Record<string, unknown>
  objective?: string
  design?: { path: string; sha: string }
  plan?: { path: string; sha: string }
}

export async function proposeBuilderJob(
  payload: ConversationProposeRequest,
): Promise<ConversationProposal> {
  return await gfetch<ConversationProposal>(
    '/builder/conversation/propose',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    20000,
  )
}

export interface ConversationApproveRequest {
  prepared_manifest: Record<string, unknown>
  expected_manifest_sha: string
  expected_base_sha: string
  approval_nonce: string
  confirmed: boolean
}

export interface ConversationApproval {
  ok: boolean
  state?: string | null
  error_code?: string | null
  error?: string | null
  next_action?: string | null
  mission_id?: string | null
  apply_status?: string
  tasks?: Array<{ packet_id: string; task_id: string }>
}

export async function approveBuilderJob(
  payload: ConversationApproveRequest,
): Promise<ConversationApproval> {
  return await gfetch<ConversationApproval>(
    '/builder/conversation/approve',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    15000,
  )
}

export interface ConversationResume {
  ok: boolean
  state?: string | null
  error_code?: string | null
  error?: string | null
  next_action?: string | null
  objective?: string | null
  mission?: { id?: string | null; manifest_sha256?: string | null; state?: string | null }
  current_work?: {
    packet_id?: string | null
    task_id?: string | null
    state?: string | null
    attempt_count?: number | null
  }
  blocker?: string | null
  pr?: {
    number?: number | null
    url?: string | null
    checks_state?: string | null
    review_state?: string | null
    merged?: boolean | null
  } | null
}

/** Recover durable Builder job state for a proposal a reloaded chat message
 *  already approved — see gateway/conversation_handoff.py's `resume`. Chat
 *  history is never the source of truth for this; only the mission id is. */
export async function resumeBuilderJob(missionId: string): Promise<ConversationResume> {
  const params = new URLSearchParams({ mission_id: missionId })
  return await gfetch<ConversationResume>(`/builder/conversation/resume?${params.toString()}`, undefined, 15000)
}

// ── Experts ────────────────────────────────────────────────────────────────────

export interface ExpertProfile {
  id: string
  label: string
  book_count: number
  tags: string[]
  formats: string[]
  sample_title: string
}

export async function fetchExpertList(): Promise<ExpertProfile[]> {
  const payload = await gfetch<{ experts: ExpertProfile[] }>('/knowledge/experts')
  return payload.experts ?? []
}

// ── Signals ────────────────────────────────────────────────────────────────────

export async function fetchSignals(): Promise<RepairsPayload> {
  try {
    return await gfetch<RepairsPayload>('/signals', undefined, 8000)
  } catch (err) {
    return { ok: false, checks_run: 0, issues: 0, repairs: [], error: describeFetchError(err, null) }
  }
}

// ── Insight loop (issue #270, IL-03) ───────────────────────────────────────────

/** Lifecycle fields carried inside an insight item's payload. */
export interface GatewayLoopInsightPayload {
  summary: string
  category: string
  return_policy: string
  return_at: string | null
  status: string
  returned_count: number
  last_returned_at: string | null
  action_id: number | null
  outcome: string | null
}

/** One insight-lifecycle item as returned by /insight-loop/*. */
export interface GatewayLoopInsight {
  id: number
  object_type: string
  source_ref: string | null
  user_review: string
  payload: GatewayLoopInsightPayload
}

export type LoopInsightChoice = 'act' | 'snooze' | 'archive'

export async function fetchInsightLoopDue(): Promise<GatewayLoopInsight[]> {
  const payload = await gfetch<unknown>('/insight-loop/due')
  if (!isRecord(payload) || !Array.isArray(payload.insights)) {
    throw new Error('Gateway /insight-loop/due returned an invalid payload')
  }
  return payload.insights as GatewayLoopInsight[]
}

/** Record Jacob's response to a returned insight. `snooze` requires
 *  snoozeUntil (ISO datetime); `archive` defaults to not_useful server-side. */
export async function respondToLoopInsight(
  itemId: number,
  choice: LoopInsightChoice,
  opts: { snoozeUntil?: string; archiveReason?: string } = {},
): Promise<GatewayLoopInsight> {
  const params = new URLSearchParams({ choice })
  if (opts.snoozeUntil) params.set('snooze_until', opts.snoozeUntil)
  if (opts.archiveReason) params.set('archive_reason', opts.archiveReason)
  const payload = await gfetch<unknown>(
    `/insight-loop/insight/${itemId}/respond?${params.toString()}`,
    { method: 'POST' },
  )
  if (!isRecord(payload) || !isRecord(payload.insight)) {
    throw new Error('Gateway /insight-loop respond returned an invalid payload')
  }
  return payload.insight as unknown as GatewayLoopInsight
}
