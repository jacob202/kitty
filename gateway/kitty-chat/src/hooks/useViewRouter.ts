'use client'
import { useCallback, useState } from 'react'

export type KittyView = 'home' | 'chat' | 'tasks' | 'tools' | 'terminal' | 'projects' |
  'docs' | 'providers' | 'agents' | 'images' | 'studio' | 'tutor' | 'settings' | 'builder'

export function useViewRouter(initialView: KittyView = 'home') {
  const [activeView, setActiveView] = useState<KittyView>(initialView)

  const navigate = useCallback((view: KittyView) => setActiveView(view), [])
  const navigateHome = useCallback(() => setActiveView('home'), [])
  const navigateChat = useCallback(() => setActiveView('chat'), [])
  const onViewChange = useCallback((view: string) => {
    if (view === 'home' || view === 'chat' || view === 'tasks' || view === 'tools' ||
        view === 'terminal' || view === 'projects' || view === 'docs' || view === 'providers' ||
        view === 'agents' || view === 'images' || view === 'studio' || view === 'tutor' || view === 'settings' ||
        view === 'builder') {
      setActiveView(view)
    }
  }, [])

  return { activeView, setActiveView: onViewChange, navigate, navigateHome, navigateChat }
}
