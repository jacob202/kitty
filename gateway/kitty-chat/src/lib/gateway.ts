/**
 * Client for Kitty's FastAPI gateway (proxied through /proxy).
 * All requests go through the Next.js proxy route so auth headers
 * stay server-side and CORS is avoided.
 */
import { KittyMood, Model, MODELS } from './types'

const BASE = '/proxy'

// ── Types ───────────────────────────────────────────────────────────────────

export interface GatewayBrief {
  date: string
  headlines: { title: string; url: string; snippet: string }[]
  memory_snippet: string
  intention: string
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
