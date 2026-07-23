'use client'

import type { ComponentType } from 'react'
import { HomeState } from '@/components/HomeState'

export type ViewId =
  | 'home' | 'chat' | 'builder' | 'settings'
  | 'work' | 'studio' | 'library'
  // Legacy — redirected:
  | 'tasks' | 'tools' | 'terminal' | 'projects' | 'docs' | 'providers' | 'agents' | 'images' | 'tutor'

export interface ViewEntry {
  component: ComponentType<any>
  title: string
  icon: string
  railSlot: boolean
}

export const VIEWS: Record<ViewId, ViewEntry> = {
  home:      { component: HomeState, title: 'Home',     icon: 'home',     railSlot: true },
  chat:      { component: HomeState, title: 'Chat',     icon: 'chat',     railSlot: true },
  work:      { component: HomeState, title: 'Work',     icon: 'work',     railSlot: true },
  studio:    { component: HomeState, title: 'Studio',   icon: 'studio',   railSlot: true },
  builder:   { component: HomeState, title: 'Builder',  icon: 'builder',  railSlot: true },
  library:   { component: HomeState, title: 'Library',  icon: 'library',  railSlot: true },
  settings:  { component: HomeState, title: 'Settings', icon: 'settings', railSlot: true },
  // Legacy redirects
  tasks:     { component: HomeState, title: 'Tasks',    icon: 'work',     railSlot: false },
  tools:     { component: HomeState, title: 'Tools',    icon: 'settings', railSlot: false },
  terminal:  { component: HomeState, title: 'Terminal', icon: 'terminal', railSlot: false },
  projects:  { component: HomeState, title: 'Projects', icon: 'library',  railSlot: false },
  docs:      { component: HomeState, title: 'Docs',     icon: 'library',  railSlot: false },
  providers: { component: HomeState, title: 'Providers',icon: 'settings', railSlot: false },
  agents:    { component: HomeState, title: 'Agents',   icon: 'settings', railSlot: false },
  images:    { component: HomeState, title: 'Images',   icon: 'studio',   railSlot: false },
  tutor:     { component: HomeState, title: 'Tutor',    icon: 'settings', railSlot: false },
}

export const RAIL_VIEWS: ViewId[] = ['home', 'chat', 'work', 'studio', 'builder', 'library', 'settings']

/** Old view ID → new view ID mapping for deep-link redirects. */
export const REDIRECTS: Record<string, ViewId> = {
  tasks: 'work',
  tools: 'settings',
  terminal: 'settings',
  projects: 'library',
  docs: 'library',
  providers: 'settings',
  agents: 'settings',
  images: 'studio',
  tutor: 'settings',
}

export function getView(id: string): ViewEntry | undefined {
  return VIEWS[id as ViewId]
}
