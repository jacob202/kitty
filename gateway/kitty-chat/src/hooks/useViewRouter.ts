'use client'
import { useCallback, useState } from 'react'

export type KittyView = 'home' | 'chat' | 'tasks' | 'work' | 'tools' | 'terminal' | 'projects' |
  'docs' | 'providers' | 'agents' | 'images' | 'studio' | 'library' | 'tutor' | 'settings' | 'builder'

export function useViewRouter(initialView: KittyView = 'home') {
  const [activeView, setActiveView] = useState<KittyView>(initialView)

  const navigate = useCallback((view: KittyView) => setActiveView(view), [])
  const navigateHome = useCallback(() => setActiveView('home'), [])
  const navigateChat = useCallback(() => setActiveView('chat'), [])
  const onViewChange = useCallback((view: string) => {
    const valid: KittyView[] = ['home', 'chat', 'work', 'tasks', 'tools', 'terminal', 'projects',
      'docs', 'providers', 'agents', 'images', 'studio', 'library', 'tutor', 'settings', 'builder']
    if (valid.includes(view as KittyView)) {
      setActiveView(view as KittyView)
    }
  }, [])

  return { activeView, setActiveView: onViewChange, navigate, navigateHome, navigateChat }
}
