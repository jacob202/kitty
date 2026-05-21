/**
 * Client for Kitty's FastAPI gateway (proxied through /proxy).
 * All requests go through the Next.js proxy route so auth headers
 * stay server-side and CORS is avoided.
 */
import { Chat, Message, KittyMood, Model, MODELS } from './types'

const BASE = '/proxy'

// ── Types ───────────────────────────────────────────────────────────────────

export interface GatewayBrief {
  date: string
  headlines: { title: string; url: string; snippet: string }[]
  memory_snippet: string
  intention: string
  generated_at?: string
  error?: string
}

export interface GatewaySearchSnapshot {
  query: string
  results: { source: string; text: string }[]
}

export interface GatewayMoodState {
  mood: KittyMood
  energy: number
  session_turns: number
  total_turns: number
  drift_count: number
  last_active_ts: number
}

// ── Helpers ─────────────────────────────────────────────────────────────────

async function gfetch(path: string, init?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(`gateway ${path} → ${res.status}`)
  return res.json()
}

// ── Exported functions ───────────────────────────────────────────────────────

export async function fetchGatewayModels(): Promise<Model[]> {
  try {
    const json = await gfetch('/v1/models')
    const ids: string[] = (json.data ?? []).map((m: { id: string }) => m.id)
    return ids
      .map(id => MODELS.find(m => m.id === id))
      .filter((m): m is Model => m != null)
      .concat(MODELS.filter(m => !ids.includes(m.id)))  // always include defaults
      .slice(0, 8)
  } catch {
    return MODELS
  }
}

export async function fetchGatewayBrief(): Promise<GatewayBrief | null> {
  try {
    return await gfetch('/brief')
  } catch {
    return null
  }
}

export async function fetchGatewaySearch(
  query: string,
  limit = 5
): Promise<GatewaySearchSnapshot | null> {
  if (!query.trim()) return null
  try {
    const params = new URLSearchParams({ q: query, limit: String(limit) })
    const json = await gfetch(`/search?${params}`)
    const raw = json.knowledge ?? json.results ?? []
    return {
      query,
      results: raw.map((r: { source?: string; text?: string }) => ({
        source: r.source ?? '',
        text: r.text ?? '',
      })),
    }
  } catch {
    return null
  }
}

export async function fetchGatewayMood(): Promise<GatewayMoodState | null> {
  try {
    return await gfetch('/mood')
  } catch {
    return null
  }
}

// ── Voice (STT / TTS) ────────────────────────────────────────────────────────

export async function transcribeAudio(blob: Blob): Promise<string> {
  const form = new FormData()
  form.append('file', blob, 'audio.webm')
  const res = await fetch(`${BASE}/v1/audio/transcriptions`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`STT ${res.status}`)
  const json = await res.json()
  return (json.text ?? '').trim()
}

export async function synthesizeSpeech(text: string, voice = 'kitty'): Promise<string> {
  const res = await fetch(`${BASE}/v1/audio/speech`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input: text, voice }),
  })
  if (!res.ok) throw new Error(`TTS ${res.status}`)
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

// ── Weather ─────────────────────────────────────────────────────────────────

export interface GatewayWeather {
  temp_c: number
  feels_like_c: number
  description: string
  humidity: number
  wind_kmph: number
  max_c: number
  min_c: number
}

export async function fetchGatewayWeather(): Promise<GatewayWeather | null> {
  try {
    const json = await gfetch('/weather')
    return json.error ? null : json as GatewayWeather
  } catch {
    return null
  }
}

// ── Calendar ────────────────────────────────────────────────────────────────

export interface CalendarEvent {
  title: string
  start: string
  end: string
}

export async function fetchCalendarToday(): Promise<CalendarEvent[]> {
  try {
    const json = await gfetch('/calendar/today')
    return json.available ? (json.events ?? []) : []
  } catch {
    return []
  }
}

// ── Task runner ─────────────────────────────────────────────────────────────

export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskType   = 'research' | 'ingest' | 'build' | 'cleanup' | 'dream'

export interface GatewayTask {
  id: string
  goal: string
  task_type: TaskType
  status: TaskStatus
  created_at: number
  started_at?: number
  completed_at?: number
  progress: string
  error: string
}

export async function createGatewayTask(goal: string, taskType: TaskType = 'research'): Promise<string | null> {
  try {
    const json = await gfetch('/task/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, task_type: taskType }),
    })
    return json.task_id ?? null
  } catch {
    return null
  }
}

export async function fetchGatewayTasks(limit = 8): Promise<GatewayTask[]> {
  try {
    const json = await gfetch(`/tasks?limit=${limit}`)
    return json.tasks ?? []
  } catch {
    return []
  }
}

export async function cancelGatewayTask(id: string): Promise<boolean> {
  try {
    await gfetch(`/task/${id}/cancel`, { method: 'POST' })
    return true
  } catch {
    return false
  }
}

// ── Web monitors ────────────────────────────────────────────────────────────

export interface GatewayMonitor {
  watch_id: string
  url: string
  label: string
  keywords: string[]
  interval_minutes: number
  last_checked?: number
  last_status?: string
  match_count: number
}

export async function fetchGatewayMonitors(): Promise<GatewayMonitor[]> {
  try {
    const json = await gfetch('/monitors')
    return json.watches ?? []
  } catch {
    return []
  }
}

export async function addGatewayMonitor(url: string, label: string, keywords: string[] = []): Promise<string | null> {
  try {
    const json = await gfetch('/monitor/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, label, keywords, interval_minutes: 60 }),
    })
    return json.watch_id ?? null
  } catch {
    return null
  }
}

export async function removeGatewayMonitor(id: string): Promise<void> {
  try { await gfetch(`/monitor/${id}`, { method: 'DELETE' }) } catch { /* non-fatal */ }
}

// ── Cron schedules ───────────────────────────────────────────────────────────

export type CronScheduleType = 'daily' | 'interval' | 'once'

export interface CronSchedule {
  id: string
  name: string
  action: string
  schedule_type: CronScheduleType
  schedule_value: string
  enabled: number
  last_run: number
  created_at: number
  metadata?: string
}

export async function fetchCronSchedules(): Promise<CronSchedule[]> {
  try {
    const json = await gfetch('/cron/schedules')
    return json.schedules ?? []
  } catch {
    return []
  }
}

export async function fetchCronActions(): Promise<string[]> {
  try {
    const json = await gfetch('/cron/actions')
    return json.actions ?? []
  } catch {
    return []
  }
}

export async function createCronSchedule(
  name: string, action: string,
  scheduleType: CronScheduleType, scheduleValue: string,
): Promise<string | null> {
  try {
    const json = await gfetch('/cron/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, action, schedule_type: scheduleType, schedule_value: scheduleValue }),
    })
    return json.schedule_id ?? null
  } catch {
    return null
  }
}

export async function deleteCronSchedule(id: string): Promise<boolean> {
  try {
    const json = await gfetch(`/cron/${id}`, { method: 'DELETE' })
    return json.deleted ?? false
  } catch {
    return false
  }
}

export async function toggleCronSchedule(id: string): Promise<boolean | null> {
  try {
    const json = await gfetch(`/cron/${id}/toggle`, { method: 'POST' })
    return json.enabled ?? null
  } catch {
    return null
  }
}

// ── Image generation ─────────────────────────────────────────────────────────

export interface ImageGenStatus {
  available: boolean
  backend: string
}

export interface ImageEntry {
  prompt_id: string
  filename: string
  prompt: string
  created_at: number
}

export async function fetchImageStatus(): Promise<ImageGenStatus> {
  try {
    return await gfetch('/image/status')
  } catch {
    return { available: false, backend: 'comfyui' }
  }
}

export async function generateImage(prompt: string): Promise<{ filename: string; prompt_id: string } | null> {
  try {
    return await gfetch('/image/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    })
  } catch {
    return null
  }
}

export async function fetchImageHistory(): Promise<ImageEntry[]> {
  try {
    const json = await gfetch('/image/history')
    return json.images ?? []
  } catch {
    return []
  }
}

// ── Agents + Skills ─────────────────────────────────────────────────────────

export interface GatewayAgent { role: string; description?: string }
export interface GatewaySkill { name: string; description?: string; enabled?: boolean }

export async function fetchGatewayAgents(): Promise<GatewayAgent[]> {
  try {
    const json = await gfetch('/agents')
    return json.agents ?? []
  } catch {
    return []
  }
}

export async function fetchGatewaySkills(): Promise<GatewaySkill[]> {
  try {
    const json = await gfetch('/skills')
    return json.skills ?? []
  } catch {
    return []
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

export async function spawnAgent(goal: string, agentType: AgentType = 'explorer'): Promise<number | null> {
  try {
    const json = await gfetch('/agent/spawn', {
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
    return await gfetch(`/agent/${sessionId}`)
  } catch {
    return null
  }
}

export async function fetchAgentSessions(limit = 10): Promise<AgentSession[]> {
  try {
    const json = await gfetch(`/agents?limit=${limit}`)
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
  status: 'pending' | 'in_progress' | 'completed' | 'deprioritized'
  active_form: string
  sort_order: number
  created_at: number
  updated_at: number
}

export async function fetchGatewayTodos(): Promise<GatewayTodo[]> {
  try {
    const json = await gfetch('/todos')
    return json.todos ?? []
  } catch {
    return []
  }
}

export async function addGatewayTodo(content: string): Promise<GatewayTodo | null> {
  try {
    return await gfetch('/todos/add', {
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
    const json = await gfetch(`/todos/${id}/complete`, { method: 'POST' })
    return json.completed ?? false
  } catch {
    return false
  }
}

export async function deleteGatewayTodo(id: number): Promise<boolean> {
  try {
    const json = await gfetch(`/todos/${id}`, { method: 'DELETE' })
    return json.deleted ?? false
  } catch {
    return false
  }
}

// ── Nudges ────────────────────────────────────────────────────────────────────

export interface GatewayNudge {
  id: string
  type: string
  message: string
}

export async function fetchGatewayNudges(): Promise<GatewayNudge[]> {
  try {
    const json = await gfetch('/nudges')
    return json.nudges ?? []
  } catch {
    return []
  }
}

export async function dismissGatewayNudge(id: string): Promise<void> {
  try { await gfetch(`/nudge/${id}/dismiss`, { method: 'POST' }) } catch { /* non-fatal */ }
}

// ── Chat persistence ─────────────────────────────────────────────────────────

function serializeChat(chat: Chat) {
  return {
    ...chat,
    createdAt: chat.createdAt.toISOString(),
    updatedAt: chat.updatedAt.toISOString(),
    messages: chat.messages.map(m => ({
      ...m,
      timestamp: m.timestamp.toISOString(),
    })),
  }
}

function deserializeChat(raw: Record<string, unknown>): Chat {
  return {
    ...(raw as Omit<Chat, 'createdAt' | 'updatedAt' | 'messages'>),
    createdAt: new Date(raw.createdAt as string),
    updatedAt: new Date(raw.updatedAt as string),
    messages: ((raw.messages ?? []) as Record<string, unknown>[]).map(m => ({
      ...(m as Omit<Message, 'timestamp'>),
      timestamp: new Date(m.timestamp as string),
    })),
  }
}

export async function loadGatewayChats(): Promise<Chat[] | null> {
  try {
    const json = await gfetch('/chats')
    return ((json.chats ?? []) as Record<string, unknown>[]).map(deserializeChat)
  } catch {
    return null
  }
}

export async function saveGatewayChat(chat: Chat): Promise<void> {
  try {
    await fetch(`${BASE}/chats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(serializeChat(chat)),
    })
  } catch { /* non-fatal */ }
}

export async function deleteGatewayChat(id: string): Promise<void> {
  try {
    await fetch(`${BASE}/chats/${id}`, { method: 'DELETE' })
  } catch { /* non-fatal */ }
}
