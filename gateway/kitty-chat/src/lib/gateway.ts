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
