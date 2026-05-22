import { MODELS, type Model } from './types'

const GATEWAY_BASE = '/proxy'
const DEFAULT_TIMEOUT_MS = 2500

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

/** When `fromLiveGateway` is false, `error` explains why; `data` is still safe to render (fallback or null). */
export type GatewayModelsPayload = {
  models: Model[]
  fromLiveGateway: boolean
  error: string | null
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

export async function fetchGatewayBrief(): Promise<GatewayBriefPayload> {
  try {
    const response = await fetchWithTimeout(`${GATEWAY_BASE}/brief`, 1500)
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
  try {
    const json = await gfetch<{ todos?: GatewayTodo[] }>('/todos')
    return json.todos ?? []
  } catch {
    return []
  }
}

export async function addGatewayTodo(content: string): Promise<GatewayTodo | null> {
  try {
    return await gfetch<GatewayTodo>('/todos/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
  } catch {
    return null
  }
}

export async function completeGatewayTodo(id: number): Promise<boolean> {
  try {
    await gfetch(`/todos/${id}/complete`, { method: 'POST' })
    return true
  } catch {
    return false
  }
}

export async function deleteGatewayTodo(id: number): Promise<boolean> {
  try {
    await gfetch(`/todos/${id}`, { method: 'DELETE' })
    return true
  } catch {
    return false
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
