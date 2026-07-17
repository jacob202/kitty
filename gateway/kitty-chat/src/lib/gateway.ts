import { MODELS, type Model } from './types'

const GATEWAY_BASE = '/proxy'
// The proxy has to cross the Next.js boundary and may wake a local gateway
// store on the first request. 2.5s made healthy features look permanently
// offline after a cold start; keep the timeout bounded but realistic.
const DEFAULT_TIMEOUT_MS = 8000

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
  }
  sections: {
    memories: string[]
    knowledge: string[]
    journal: string[]
    todos: string[]
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

export interface BuilderAttemptStatus {
  id: number
  number: number
  outcome: 'succeeded' | 'failed' | 'aborted' | 'crashed' | null
  implementation_status: string | null
  validation_status: 'passed' | 'failed' | 'skipped' | null
  review_verdict: 'approve' | 'request_changes' | 'reject' | null
  lease_id: number | null
  created_at: string | null
  updated_at: string | null
}

export interface BuilderPacketStatus {
  packet_id: string
  title: string
  task_id: string
  task_state: string | null
  depends_on: string[]
  eligibility: { state: 'eligible' | 'waiting' | 'blocked' | 'not_queued' | 'unavailable'; blocked_by: string[] }
  budget: { used: number; max: number; exhausted: boolean }
  attempt: BuilderAttemptStatus | null
  previous_attempt: BuilderAttemptStatus | null
  lease: { id: number; worker_id: string; branch: string; base_sha: string; created_at: string | null } | null
  run: {
    id: string
    state: string
    started_at: string | null
    last_heartbeat_at: string | null
    ended_at: string | null
    exit_code: number | null
  } | null
  publication: { pr_url: string | null; checks_state: string | null; review_state: string | null; merged: boolean } | null
  last_event: {
    id: number
    type: string
    created_at: string | null
    reason: string | null
    counts_toward_budget: boolean | null
  } | null
  failure_kind: 'implementation' | 'identity' | 'validation' | 'review' | 'infrastructure' | 'cancelled' | 'exhausted' | null
  blocked_reason: string | null
  last_error: string | null
  updated_at: string | null
  base_sha: string | null
}

export interface BuilderInitiativeStatus {
  initiative_id: string
  title: string
  state: 'active' | 'paused' | 'completed' | 'failed'
  pause_reason: string | null
  next_packet: string | null
  counts: BuilderQueueStatus & { exhausted: number }
  created_at: string | null
  updated_at: string | null
  packets: BuilderPacketStatus[]
}

export interface BuilderStatusSnapshot {
  schema_version: number
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
  fromLiveGateway: boolean
  error: string | null
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

export function buildGatewayModels(ids: string[]): Model[] {
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
      name: prettyModelName(id),
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

  return {
    query: (raw.query ?? '').trim(),
    counts: {
      memories: memories.length,
      knowledge: knowledge.length,
      journal: journal.length,
      todos: todos.length,
    },
    sections: {
      memories,
      knowledge,
      journal,
      todos,
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
    const ids = Array.isArray(json?.data)
      ? json.data.map((model: { id?: string }) => model?.id).filter((id: unknown): id is string => typeof id === 'string')
      : []
    return {
      models: buildGatewayModels(ids),
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

export async function spawnAgent(goal: string, agentType: AgentType = 'explorer'): Promise<number | null> {
  try {
    const json = await gfetch<{ session_id?: number }>('/agent/spawn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, agent_type: agentType }),
    })
    return json.session_id ?? null
  } catch {
    return null
  }
}

export async function fetchAgentStatus(sessionId: number): Promise<AgentSession | null> {
  try {
    return await gfetch<AgentSession>(`/agent/${sessionId}`)
  } catch {
    return null
  }
}

export async function fetchAgentSessions(limit = 10): Promise<AgentSession[]> {
  try {
    const json = await gfetch<{ agents?: AgentSession[] }>(`/agents?limit=${limit}`)
    return json.agents ?? []
  } catch {
    return []
  }
}

export async function stopAgent(sessionId: number): Promise<boolean> {
  try {
    await gfetch(`/agent/${sessionId}/stop`, { method: 'POST' })
    return true
  } catch {
    return false
  }
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

export async function completeGatewayTodo(id: number): Promise<boolean> {
  await gfetch(`/todos/${id}/complete`, { method: 'POST' })
  return true
}

export async function deleteGatewayTodo(id: number): Promise<boolean> {
  await gfetch(`/todos/${id}`, { method: 'DELETE' })
  return true
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
  try {
    const json = await gfetch<{ templates?: GatewayPromptTemplate[] }>('/prompts')
    return json.templates ?? []
  } catch {
    return []
  }
}

// ── Tasks ────────────────────────────────────────────────────────────────────

export type TaskType = 'research' | 'ingest' | 'build' | 'cleanup' | 'dream'

export interface GatewayTask {
  task_id: string
  goal: string
  task_type: string
  status: string
  created_at?: number
  updated_at?: number
  error?: string | null
}

export async function fetchGatewayTasks(limit = 20): Promise<GatewayTask[]> {
  try {
    const json = await gfetch<{ tasks?: GatewayTask[] }>(`/tasks?limit=${limit}`)
    return json.tasks ?? []
  } catch {
    return []
  }
}

export async function createGatewayTask(
  goal: string,
  taskType: TaskType = 'research',
): Promise<string | null> {
  try {
    const json = await gfetch<{ task_id?: string }>('/task/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, task_type: taskType }),
    })
    return json.task_id ?? null
  } catch {
    return null
  }
}

export async function cancelGatewayTask(taskId: string): Promise<boolean> {
  try {
    await gfetch(`/task/${taskId}/cancel`, { method: 'POST' })
    return true
  } catch {
    return false
  }
}

// ── Monitors ─────────────────────────────────────────────────────────────────

export interface GatewayMonitor {
  watch_id: string
  url: string
  label: string
  keywords?: string[]
  interval_minutes?: number
  last_checked?: number | null
  last_hash?: string | null
  last_match?: string | null
}

export async function fetchGatewayMonitors(): Promise<GatewayMonitor[]> {
  try {
    const json = await gfetch<{ watches?: GatewayMonitor[] }>('/monitors')
    return json.watches ?? []
  } catch {
    return []
  }
}

export async function addGatewayMonitor(url: string, label: string): Promise<string | null> {
  try {
    const json = await gfetch<{ watch_id?: string }>('/monitor/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, label }),
    })
    return json.watch_id ?? null
  } catch {
    return null
  }
}

export async function removeGatewayMonitor(watchId: string): Promise<boolean> {
  try {
    await gfetch(`/monitor/${watchId}`, { method: 'DELETE' })
    return true
  } catch {
    return false
  }
}

export async function fetchGatewaySearch(
  query: string,
  limit = 5,
  signal?: AbortSignal,
): Promise<GatewaySearchPayload> {
  const q = query.trim()
  if (!q) {
    return { snapshot: null, fromLiveGateway: true, error: null }
  }

  try {
    const response = await fetchWithTimeout(
      `${GATEWAY_BASE}/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      4000,
      signal,
    )
    if (!response.ok) {
      return {
        snapshot: null,
        fromLiveGateway: false,
        error: describeFetchError(null, response),
      }
    }
    const json = await response.json()
    return {
      snapshot: summarizeGatewaySearch({
        query: q,
        memories: json?.memories,
        knowledge: json?.knowledge,
        journal: json?.journal,
        todos: json?.todos,
      }),
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      if (signal?.aborted) {
        return { snapshot: null, fromLiveGateway: true, error: null }
      }
      return {
        snapshot: null,
        fromLiveGateway: false,
        error: 'Request timed out — is the Kitty gateway running?',
      }
    }
    return {
      snapshot: null,
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

export async function toggleGatewayLoop(loopId: string): Promise<boolean> {
  try {
    await gfetch(`/loop/${loopId}/toggle`, { method: 'POST' })
    return true
  } catch {
    return false
  }
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

export async function dismissGatewayInsight(insightId: string): Promise<boolean> {
  try {
    await gfetch(`/insight/${insightId}/dismiss`, { method: 'POST' })
    return true
  } catch {
    return false
  }
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
  try {
    const json = await gfetch<{ schedules?: CronSchedule[] }>('/cron/schedules')
    return json.schedules ?? []
  } catch {
    return []
  }
}

export async function fetchCronActions(): Promise<string[]> {
  try {
    const json = await gfetch<{ actions?: string[] }>('/cron/actions')
    return json.actions ?? []
  } catch {
    return []
  }
}

export async function createCronSchedule(
  name: string,
  action: string,
  scheduleType: CronScheduleType,
  scheduleValue: string,
): Promise<string | null> {
  try {
    const json = await gfetch<{ id?: string }>('/cron/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, action, schedule_type: scheduleType, schedule_value: scheduleValue }),
    })
    return json.id ?? null
  } catch {
    return null
  }
}

export async function deleteCronSchedule(id: string): Promise<boolean> {
  try {
    await gfetch(`/cron/schedule/${id}`, { method: 'DELETE' })
    return true
  } catch {
    return false
  }
}

export async function updateCronSchedule(
  id: string,
  name: string,
  action: string,
  scheduleType: CronScheduleType,
  scheduleValue: string,
): Promise<boolean> {
  await gfetch(`/cron/schedule/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, action, schedule_type: scheduleType, schedule_value: scheduleValue }),
  })
  return true
}

export async function toggleCronSchedule(id: string): Promise<boolean> {
  try {
    await gfetch(`/cron/schedule/${id}/toggle`, { method: 'POST' })
    return true
  } catch {
    return false
  }
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
  filename: string
  prompt: string
  created_at?: number
}

export async function fetchImageStatus(): Promise<{ available: boolean }> {
  try {
    const json = await gfetch<{ available?: boolean }>('/image/status')
    return { available: json.available === true }
  } catch {
    return { available: false }
  }
}

export async function generateImage(prompt: string): Promise<{ filename: string } | null> {
  try {
    return await gfetch<{ filename: string }>('/image/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    })
  } catch {
    return null
  }
}

export async function fetchImageHistory(limit = 20): Promise<ImageEntry[]> {
  try {
    const json = await gfetch<{ images?: ImageEntry[] }>(`/image/history?limit=${limit}`)
    return json.images ?? []
  } catch {
    return []
  }
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

export async function approveAction(id: number): Promise<void> {
  await gfetch(`/actions/${id}/approve`, { method: 'POST' })
}

export async function rejectAction(id: number): Promise<void> {
  await gfetch(`/actions/${id}/reject`, { method: 'POST' })
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
): Promise<CaptureResult | null> {
  const formData = new FormData()
  formData.append('file', file)
  if (opts?.conversationId) formData.append('conversation_id', opts.conversationId)
  if (opts?.projectId !== undefined) formData.append('project_id', String(opts.projectId))
  try {
    return await gfetch<CaptureResult>('/capture/file', {
      method: 'POST',
      body: formData,
    })
  } catch {
    return null
  }
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

// Projects/knowledge/provider fetchers throw on failure — react-query's
// isError is the honest signal, not a silently empty list.
export async function fetchProjects(): Promise<GatewayProject[]> {
  const json = await gfetch<{ projects?: GatewayProject[] }>('/projects')
  return json.projects ?? []
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
