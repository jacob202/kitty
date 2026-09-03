'use client'

import type { ComponentType } from 'react'

import { AgentWorkspacePanel } from '@/components/AgentWorkspacePanel'

export type ViewId =
  | 'home' | 'chat' | 'builder' | 'builder-details' | 'settings'
  | 'work' | 'studio' | 'library' | 'automations'
  | 'tasks' | 'tools' | 'terminal' | 'projects' | 'docs' | 'providers' | 'agents' | 'agent-sessions' | 'images' | 'tutor' | 'journal' | 'research'

export interface ViewEntry {
  component: ComponentType<any>
  title: string
  icon: string
  railSlot: boolean
}

function PlaceholderView() {
  return <div style={{ padding: 24, fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink-2)' }}>loading...</div>
}

export const VIEWS: Record<ViewId, ViewEntry> = {
  home:      { component: PlaceholderView, title: 'Home',     icon: 'home',     railSlot: true },
  chat:      { component: PlaceholderView, title: 'Chat',     icon: 'chat',     railSlot: true },
  work:      { component: PlaceholderView, title: 'Work',     icon: 'work',     railSlot: true },
  studio:    { component: PlaceholderView, title: 'Studio',   icon: 'studio',   railSlot: true },
  builder:   { component: PlaceholderView, title: 'Builder',  icon: 'builder',  railSlot: true },
  'builder-details': { component: PlaceholderView, title: 'Builder details', icon: 'builder', railSlot: false },
  library:   { component: PlaceholderView, title: 'Library',  icon: 'library',  railSlot: true },
  automations:{ component: PlaceholderView, title: 'Automations', icon: 'work', railSlot: true },
  settings:  { component: PlaceholderView, title: 'Settings', icon: 'settings', railSlot: true },
  tasks:     { component: PlaceholderView, title: 'Tasks',    icon: 'work',     railSlot: false },
  tools:     { component: PlaceholderView, title: 'Tools',    icon: 'settings', railSlot: false },
  terminal:  { component: PlaceholderView, title: 'Terminal', icon: 'terminal', railSlot: false },
  projects:  { component: PlaceholderView, title: 'Projects', icon: 'library',  railSlot: false },
  docs:      { component: PlaceholderView, title: 'Docs',     icon: 'library',  railSlot: false },
  providers: { component: PlaceholderView, title: 'Providers',icon: 'settings', railSlot: false },
  agents:    { component: AgentWorkspacePanel, title: 'Agents', icon: 'settings', railSlot: false },
  'agent-sessions': { component: PlaceholderView, title: 'Agent session', icon: 'settings', railSlot: false },
  images:    { component: PlaceholderView, title: 'Images',   icon: 'studio',   railSlot: false },
  tutor:     { component: PlaceholderView, title: 'Tutor',    icon: 'settings', railSlot: false },
  journal:   { component: PlaceholderView, title: 'Journal',  icon: 'settings', railSlot: false },
  research:  { component: PlaceholderView, title: 'Research', icon: 'library', railSlot: false },
}

export const RAIL_VIEWS: ViewId[] = ['home', 'chat', 'work', 'projects', 'studio', 'library', 'automations', 'settings']

export const REDIRECTS: Record<string, ViewId> = {
  builder: 'work',
  tools: 'settings',
  terminal: 'terminal',
  projects: 'projects',
  docs: 'library',
  providers: 'settings',
  agents: 'agents',
  images: 'studio',
  tutor: 'tutor',
  journal: 'journal',
}

export function getView(id: string): ViewEntry | undefined {
  return VIEWS[id as ViewId]
}
