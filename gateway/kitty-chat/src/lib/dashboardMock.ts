export type DashboardTone = 'gentle' | 'direct' | 'blunt'

export const commandZones = [
  { label: 'plan my day',     prompt: 'Help me plan my day.',                     accent: 'var(--teal)' },
  { label: 'quick journal',   prompt: 'Let\'s do a quick journal check-in.',       accent: 'var(--purple)' },
  { label: 'deep focus',      prompt: 'I need to focus. What should I work on?',  accent: 'var(--orange)' },
  { label: 'what\'s next',    prompt: 'What\'s the most important thing right now?', accent: 'var(--indigo)' },
]

export const contextFound = [
  { label: 'memory',    value: 'loaded',      accent: 'var(--teal)' },
  { label: 'knowledge', value: 'ready',       accent: 'var(--indigo)' },
  { label: 'journal',   value: 'last entry',  accent: 'var(--purple)' },
  { label: 'traces',    value: 'available',   accent: 'var(--orange)' },
]

export const continueItems = [
  { label: 'last session',  value: 'yesterday evening',   accent: 'var(--teal)' },
  { label: 'open thread',   value: 'ready to resume',     accent: 'var(--purple)' },
  { label: 'recent topic',  value: 'see chat history',    accent: 'var(--orange)' },
]

export const signals = [
  { label: 'gateway',  value: ':5001 up',    accent: 'var(--teal)' },
  { label: 'litellm',  value: ':8001 ready', accent: 'var(--indigo)' },
  { label: 'model',    value: 'kitty-default', accent: 'var(--purple)' },
]

export const realityCheck: Record<DashboardTone, string> & { tones: { id: DashboardTone; label: string }[] } = {
  tones: [
    { id: 'gentle', label: 'gentle' },
    { id: 'direct', label: 'direct' },
    { id: 'blunt',  label: 'blunt' },
  ],
  gentle: "You're doing fine. One thing at a time.",
  direct: "You have things to do. Start with the smallest one.",
  blunt:  "Stop thinking about it. Pick something and go.",
}
