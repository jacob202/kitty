'use client'

import React, { type ComponentType } from 'react'
import { HomeState } from '@/components/HomeState'

export type ViewId =
  | 'home' | 'chat' | 'builder' | 'settings'
  | 'work' | 'studio' | 'library'
  | 'tasks' | 'tools' | 'terminal' | 'projects' | 'docs' | 'providers' | 'agents' | 'images' | 'tutor'

export interface ViewEntry {
  component: ComponentType<any>
  title: string
  icon: string
  railSlot: boolean
}

function PlaceholderView(): React.ReactElement {
  return <div />
}

export const VIEWS: Record<ViewId, ViewEntry> = {
  home:      { component: HomeState,       title: 'Home',     icon: 'home',     railSlot: true },
  chat:      { component: PlaceholderView, title: 'Chat',     icon: 'chat',     railSlot: true },
  work:      { component: PlaceholderView, title: 'Work',     icon: 'work',     railSlot: true },
  studio:    { component: PlaceholderView, title: 'Studio',   icon: 'studio',   railSlot: true },
  builder:   { component: PlaceholderView, title: 'Builder',  icon: 'builder',  railSlot: true },
  library:   { component: PlaceholderView, title: 'Library',  icon: 'library',  railSlot: true },
  settings:  { component: PlaceholderView, title: 'Settings', icon: 'settings', railSlot: true },
  tasks:     { component: PlaceholderView, title: 'Tasks',    icon: 'work',     railSlot: false },
  tools:     { component: PlaceholderView, title: 'Tools',    icon: 'settings', railSlot: false },
  terminal:  { component: PlaceholderView, title: 'Terminal', icon: 'terminal', railSlot: false },
  projects:  { component: PlaceholderView, title: 'Projects', icon: 'library',  railSlot: false },
  docs:      { component: PlaceholderView, title: 'Docs',     icon: 'library',  railSlot: false },
  providers: { component: PlaceholderView, title: 'Providers',icon: 'settings', railSlot: false },
  agents:    { component: PlaceholderView, title: 'Agents',   icon: 'settings', railSlot: false },
  images:    { component: PlaceholderView, title: 'Images',   icon: 'studio',   railSlot: false },
  tutor:     { component: PlaceholderView, title: 'Tutor',    icon: 'settings', railSlot: false },
}

export const RAIL_VIEWS: ViewId[] = ['home', 'chat', 'work', 'studio', 'builder', 'library', 'settings']

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
