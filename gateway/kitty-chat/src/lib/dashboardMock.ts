export type DashboardTone = 'gentle' | 'direct'

export interface DashboardItem {
  label: string
  value: string
  detail: string
  accent: string
}

export interface CommandZone {
  label: string
  prompt: string
  accent: string
}

export const nowItems: DashboardItem[] = [
  {
    label: 'Runtime',
    value: 'Gateway ready',
    detail: 'Kitty FastAPI is the source for live tools and context.',
    accent: 'var(--teal)',
  },
  {
    label: 'Focus',
    value: 'UI polish',
    detail: 'Finish the companion cockpit before deeper plumbing.',
    accent: 'var(--orange)',
  },
  {
    label: 'Next',
    value: 'Backend wiring',
    detail: 'Proxy and gateway contracts move after the surface is clean.',
    accent: 'var(--indigo)',
  },
]

export const continueItems: DashboardItem[] = [
  {
    label: 'Polish lane',
    value: 'Home dashboard',
    detail: 'Replace the weather/news shell with Now, Continue, Signals, and Commands.',
    accent: 'var(--pink-blue)',
  },
  {
    label: 'Plumbing lane',
    value: 'Gateway proxy',
    detail: 'Point KittyChat at the current 127.0.0.1:8000 backend.',
    accent: 'var(--mint)',
  },
  {
    label: 'Architecture lane',
    value: 'Runtime contracts',
    detail: 'Confirm which calls belong to Kitty Gateway, LiteLLM, and Open WebUI.',
    accent: 'var(--yellow)',
  },
]

export const signals: DashboardItem[] = [
  {
    label: 'Tests',
    value: 'TypeScript clean',
    detail: 'Last handoff reported zero TypeScript errors.',
    accent: 'var(--mint)',
  },
  {
    label: 'Context',
    value: 'Four-column shell',
    detail: 'Rail, sessions, center canvas, and right panel are already wired.',
    accent: 'var(--purple)',
  },
  {
    label: 'Risk',
    value: 'Old ports',
    detail: 'Some code still assumed the legacy 5001 backend.',
    accent: 'var(--c-yellow)',
  },
]

export const commandZones: CommandZone[] = [
  {
    label: 'Debug',
    prompt: 'Help me debug this error:\n',
    accent: 'var(--c-yellow)',
  },
  {
    label: 'Plan',
    prompt: 'Plan the next slice for ',
    accent: 'var(--indigo)',
  },
  {
    label: 'Build',
    prompt: 'Build this feature:\n',
    accent: 'var(--teal)',
  },
  {
    label: 'Review',
    prompt: 'Review this for bugs and missing tests:\n',
    accent: 'var(--orange)',
  },
]

export const suggestedFix = {
  title: 'Suggested fix',
  headline: 'Point the chat proxy at the live gateway.',
  body: 'The current architecture doc says Kitty Gateway runs on 127.0.0.1:8000. The Next proxy should default there so UI plumbing starts from the right backend.',
  action: 'Patch proxy default',
}

export const realityCheck = {
  gentle:
    'The surface is close: the shell is built, and this pass turns the home screen into the command center it was meant to be.',
  direct:
    'The old home content is the mismatch. Remove live weather/news, make the dashboard own the first screen, then wire backend calls against port 8000.',
  tones: [
    { id: 'gentle' as const, label: 'Gentle' },
    { id: 'direct' as const, label: 'Direct' },
  ],
}

export const insights: DashboardItem[] = [
  {
    label: 'Design',
    value: 'Dashboard first',
    detail: 'The first screen should show what matters now, not generic feeds.',
    accent: 'var(--pink-blue)',
  },
  {
    label: 'Flow',
    value: 'Continue over browse',
    detail: 'Recent work and suggested next action should be one click away.',
    accent: 'var(--teal)',
  },
]

export const contextFound: DashboardItem[] = [
  {
    label: 'Current docs',
    value: 'Gateway :8000',
    detail: 'docs/ARCHITECTURE.md is the live port authority.',
    accent: 'var(--orange)',
  },
  {
    label: 'Repo state',
    value: 'Next app at :4000',
    detail: 'KittyChat lives under gateway/kitty-chat with its own build and tests.',
    accent: 'var(--indigo)',
  },
  {
    label: 'Handoff',
    value: 'UI polish next',
    detail: 'BriefPanel, ChatMessage, and proxy route were the named follow-ups.',
    accent: 'var(--mint)',
  },
]
