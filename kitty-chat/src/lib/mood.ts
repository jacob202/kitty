import { KittyMood, Message } from './types'

export function inferMood(content: string, role: 'user' | 'assistant'): KittyMood {
  if (role === 'user') return 'idle'
  const lower = content.toLowerCase()
  if (lower.includes('error') || lower.includes("i'm not sure") || lower.includes("i don't know")) return 'confused'
  if (lower.includes('searching') || lower.includes('looking up') || lower.includes('retrieving')) return 'searching'
  if (lower.includes('done') || lower.includes('complete') || lower.includes('here you go') || lower.includes('finished')) return 'success'
  return 'idle'
}

// sprite sheet position for kitty-states.png (2×2 grid: TL=heroic, TR=cockpit, BL=derpy, BR=big-eye)
export const MOOD_SPRITE: Record<KittyMood, string> = {
  idle:      '0% 0%',
  thinking:  '100% 0%',
  confused:  '0% 100%',
  searching: '100% 100%',
  success:   '0% 0%',  // uses kitty-mission.png instead
}

export function getLastMood(messages: Message[]): KittyMood {
  const last = [...messages].reverse().find(m => m.role === 'assistant')
  return last?.mood ?? 'idle'
}
