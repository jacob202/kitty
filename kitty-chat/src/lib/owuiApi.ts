// All requests route through /proxy — key stays server-side
const BASE = '/proxy'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

async function del(path: string): Promise<boolean> {
  const r = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  return r.ok
}

// ── Types ────────────────────────────────────────────────────

export interface OWUIChat {
  id: string
  title: string
  updated_at: number
  created_at: number
  models?: string[]
}

export interface OWUIChatFull {
  id: string
  title: string
  models?: string[]
  chat: {
    messages: OWUIMessage[]
    models?: string[]
    history?: { messages: Record<string, OWUIMessage>; currentId: string | null }
  }
}

export interface OWUIMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: number
  model?: string
  rating?: 1 | -1
}

export interface OWUIPrompt {
  command: string
  title: string
  content: string
  timestamp: number
}

export interface OWUITool {
  id: string
  name: string
  meta: { description: string }
  updated_at?: number
}

export interface OWUIFunction {
  id: string
  name: string
  type: 'function' | 'filter' | 'action' | 'pipe'
  meta: { description: string }
  is_active: boolean
}

export interface OWUIModel {
  id: string
  name: string
  owned_by?: string
  info?: {
    meta?: {
      description?: string
      profile_image_url?: string
      tags?: { name: string }[]
    }
  }
  size?: number
  details?: { parameter_size?: string; family?: string }
}

export interface OWUIUserSettings {
  ui?: {
    default_model?: string
    models?: string[]
    system_prompt?: string
    params?: Record<string, unknown>
  }
}

// ── API ──────────────────────────────────────────────────────

export const owuiApi = {
  // Chats
  async listChats(): Promise<OWUIChat[]> {
    const r = await get<OWUIChat[] | { data: OWUIChat[] }>('/api/v1/chats/')
    return Array.isArray(r) ? r : (r as { data: OWUIChat[] }).data ?? []
  },

  async getChat(id: string): Promise<OWUIChatFull> {
    return get(`/api/v1/chats/${id}`)
  },

  async createChat(title: string, modelId: string, messages: OWUIMessage[]) {
    return post<OWUIChatFull>('/api/v1/chats/new', {
      chat: { title, models: [modelId], messages },
    })
  },

  async updateChat(id: string, title: string, modelId: string, messages: OWUIMessage[]) {
    return post<OWUIChatFull>(`/api/v1/chats/${id}`, {
      chat: { title, models: [modelId], messages },
    })
  },

  async deleteChat(id: string): Promise<boolean> {
    return del(`/api/v1/chats/${id}`)
  },

  // Prompts
  async listPrompts(): Promise<OWUIPrompt[]> {
    return get('/api/v1/prompts/')
  },

  async getPromptByCommand(command: string): Promise<OWUIPrompt> {
    return get(`/api/v1/prompts/command/${command}`)
  },

  // Tools
  async listTools(): Promise<OWUITool[]> {
    return get('/api/v1/tools/')
  },

  // Functions / Skills
  async listFunctions(): Promise<OWUIFunction[]> {
    return get('/api/v1/functions/')
  },

  // Models
  async listModels(): Promise<OWUIModel[]> {
    const r = await get<{ data: OWUIModel[] }>('/api/models')
    return r.data ?? []
  },

  async deleteModel(id: string): Promise<boolean> {
    return del(`/api/v1/models/delete?id=${encodeURIComponent(id)}`)
  },

  // Review / Rating
  async rateMessage(chatId: string, messageId: string, rating: 1 | -1) {
    return post(`/api/v1/chats/${chatId}/messages/${messageId}/rating`, { rating })
  },

  // User settings
  async getSettings(): Promise<OWUIUserSettings> {
    return get('/api/v1/users/settings')
  },

  async updateSettings(s: OWUIUserSettings) {
    return post('/api/v1/users/settings/update', s)
  },
}

export { streamChat } from './openwebui'
