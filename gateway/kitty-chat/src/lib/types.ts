export type KittyMood = 'idle' | 'thinking' | 'success' | 'confused' | 'searching'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  mood?: KittyMood
  tags?: string[]
}

export interface Chat {
  id: string
  title: string
  messages: Message[]
  model: string
  color: ChatColor
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
