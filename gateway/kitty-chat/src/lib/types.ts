export type KittyMood = 'idle' | 'thinking' | 'success' | 'confused' | 'searching'

/** A durable artifact linked to a chat message by the user who attached it. */
export interface MessageAttachment {
  id: string
  display_name: string
  media_type: string
  size?: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  mood?: KittyMood
  tags?: string[]
  attachments?: MessageAttachment[]
  /** Raw reasoning/thinking from the model (Claude extended thinking, DeepSeek R1, etc.) */
  thinking?: string
  /** Memory items surfaced from the context assembler for this response. */
  memoryItems?: MemoryItem[]
  /** Terminal status of the lifecycle turn that produced this message. */
  turnStatus?: 'running' | 'succeeded' | 'failed' | 'interrupted' | 'cancelled'
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

export interface MemoryItem {
  source: string
  text: string
  id?: string
}

export interface Chat {
  id: string
  title: string
  messages: Message[]
  model: string
  color: ChatColor
  objective?: string | null
  createdAt: Date
  updatedAt: Date
}

export type ChatColor = 'teal' | 'purple' | 'blue' | 'mint' | 'orange'

export interface Model {
  id: string
  name: string
  color: string
  glow: string
}

export const MODELS: Model[] = [
  { id: 'claude-sonnet-4-6', name: 'sonnet-4',  color: '#a884ff', glow: '#a884ff99' },
  { id: 'claude-opus-4-7',   name: 'opus-4',    color: '#21bdd9', glow: '#21bdd999' },
  { id: 'claude-haiku-4-5',  name: 'haiku-4',   color: '#9be86b', glow: '#9be86b99' },
  { id: 'gpt-4o',            name: 'gpt-4o',    color: '#f4c542', glow: '#f4c54299' },
  { id: 'deepseek-v3',       name: 'deepseek',  color: '#ff5577', glow: '#ff557799' },
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

export type KittyMode = 'gentle' | 'balanced' | 'blunt' | 'auto'

export type ReasoningLevel = 'off' | 'normal' | 'deep'

export const REASONING_LEVELS: { id: ReasoningLevel; label: string }[] = [
  { id: 'off', label: 'off' },
  { id: 'normal', label: 'normal' },
  { id: 'deep', label: 'deep' },
]

/** Returns true if the model id is known to support a reasoning/thinking knob. */
export function modelSupportsReasoning(modelId: string): boolean {
  const lower = modelId.toLowerCase()
  return lower.includes('claude')
    || lower.includes('o1')
    || lower.includes('o3')
    || (lower.includes('deepseek') && (lower.includes('r1') || lower.includes('reasoner')))
}

export type NavTab = 'chats' | 'journal' | 'knowledge' | 'tasks'

export interface TerminalState {
  expanded: boolean
  height: number
  pendingPrompt: string
}
