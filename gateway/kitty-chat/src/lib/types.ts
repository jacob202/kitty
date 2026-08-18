export type KittyMood = 'idle' | 'thinking' | 'success' | 'confused' | 'searching'

/** A durable artifact linked to a chat message by the user who attached it. */
export interface MessageAttachment {
  id: string
  display_name: string
  media_type: string
  size?: number
}

/** A prompt-injected memory, optionally linked to its durable delete target. */
export interface MemoryEvidence {
  text: string
  memoryId?: string
}

/** Accept current records and legacy string-only memory evidence from storage. */
export function normalizeMemoryEvidence(value: unknown): MemoryEvidence[] {
  if (!Array.isArray(value)) return []

  return value.flatMap((item): MemoryEvidence[] => {
    if (typeof item === 'string' && item) return [{ text: item }]
    if (!item || typeof item !== 'object' || Array.isArray(item)) return []

    const record = item as { text?: unknown; memory_id?: unknown; memoryId?: unknown }
    if (typeof record.text !== 'string' || !record.text) return []
    const memoryId = record.memory_id ?? record.memoryId
    if (memoryId === undefined) return [{ text: record.text }]
    if (typeof memoryId !== 'string' || !memoryId) return []
    return [{ text: record.text, memoryId }]
  })
}

export interface ToolCall {
  id: string
  name: string
  arguments: string
  status?: 'pending' | 'running' | 'done' | 'error'
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  provider?: string
  requestedModel?: string
  toolsState?: 'available' | 'unavailable'
  mood?: KittyMood
  tags?: string[]
  attachments?: MessageAttachment[]
  toolCalls?: ToolCall[]
  /** Terminal status of the lifecycle turn that produced this message. */
  turnStatus?: 'running' | 'succeeded' | 'failed' | 'interrupted' | 'cancelled'
  /**
   * Memory records that informed this assistant reply — the CR-04 stream
   * trailer, already policy/privacy/budget-gated server-side. Absent when no
   * memories were injected into the completion.
   */
  memoryItems?: MemoryEvidence[]
  /**
   * Council routing metadata — which expert/agent produced each part of the
   * answer. Present when a reply is assembled from multiple routed tasks; lets
   * the UI show *who* answered so the user can trust the result. The `model`
   * field above is the fallback attribution when a single model answered.
   */
  routing?: MessageRouting[]
}

/** One routed task in a Council-assembled answer. Mirrors the gateway /council `routing` field. */
export interface MessageRouting {
  task_id: string
  category: string
  agent: string
  priority: number
}

export type MessageBranch = { messages: Message[]; timestamp: Date }

export interface Chat {
  id: string
  title: string
  messages: Message[]
  model: string
  color: ChatColor
  createdAt: Date
  updatedAt: Date
  objective?: string | null
  expertId?: string | null
  systemPrompt?: string | null
  pinned?: boolean
  /** Retry branches keyed by user-message index → list of prior assistant message arrays. */
  retryBranches?: Record<number, Message[][]>
}

export type ChatColor = 'teal' | 'purple' | 'blue' | 'mint' | 'orange'

export interface Model {
  /** Selectable Kitty route (for example kitty-code), not necessarily an upstream provider model id. */
  id: string
  name: string
  color: string
  glow: string
  purpose?: string
  provider?: string | null
  upstreamModel?: string | null
  contextLength?: number | null
  inputUsdPerMillion?: number | null
  outputUsdPerMillion?: number | null
  capabilities?: string[]
  catalogueState?: string
}

/** Safe cold-start routes. Live curated picker data replaces their metadata when available. */
export const MODELS: Model[] = [
  { id: 'kitty-default', name: 'Daily Kitty', color: '#a884ff', glow: '#a884ff99', purpose: 'Choose the right lane for the turn.' },
  { id: 'kitty-small', name: 'Quick', color: '#9be86b', glow: '#9be86b99', purpose: 'Routine bounded work where speed and cost matter.' },
  { id: 'kitty-think', name: 'Think', color: '#21bdd9', glow: '#21bdd999', purpose: 'Planning, architecture, synthesis, and difficult debugging.' },
  { id: 'kitty-code', name: 'Code', color: '#4d9fff', glow: '#4d9fff99', purpose: 'Repository implementation, debugging, and verified patches.' },
  { id: 'kitty-vision', name: 'Vision', color: '#f4c542', glow: '#f4c54299', purpose: 'Screenshots, documents, photographs, and multimodal turns.' },
]

export const CHAT_COLORS: Record<ChatColor, { border: string; glow: string; tab: string }> = {
  teal:   { border: '#21bdd9', glow: '#21bdd966', tab: '#21bdd9' },
  purple: { border: '#a884ff', glow: '#a884ff66', tab: '#a884ff' },
  blue:   { border: '#4d9fff', glow: '#4d9fff66', tab: '#4d9fff' },
  mint:   { border: '#9be86b', glow: '#9be86b66', tab: '#9be86b' },
  orange: { border: '#ff7a1a', glow: '#ff7a1a66', tab: '#ff7a1a' },
}

export const COLOR_CYCLE: ChatColor[] = ['teal', 'purple', 'blue', 'mint', 'orange']

export const STREAMING_LABEL = 'thinking…'

/**
 * One proactive expert signal from the gateway signal store (CR-03). Mirrors
 * the wire shape of GET /experts/signals/unprocessed; `source` is always
 * `expert.<expert_id>` and suggestion payloads carry headline/action/analysis.
 */
export interface ExpertSignal {
  id: number
  ts: number
  source: string
  kind: string
  payload: {
    headline?: string
    action?: string
    analysis?: string
    topic_hash?: string
  }
}

export type KittyMode = 'gentle' | 'balanced' | 'blunt' | 'auto'

export type NavTab = 'chats' | 'journal' | 'knowledge' | 'tasks'

export interface TerminalState {
  expanded: boolean
  height: number
  pendingPrompt: string
}
