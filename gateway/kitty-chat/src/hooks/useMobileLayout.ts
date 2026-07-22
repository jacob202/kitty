'use client'
import { useCallback, useEffect, useState } from 'react'

const MOBILE_BREAKPOINT = 900

export function useMobileLayout() {
  const [isMobile, setIsMobile] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const media = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`)
    const sync = () => setIsMobile(media.matches)
    sync()
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', sync)
      return () => media.removeEventListener('change', sync)
    }
    media.addListener(sync)
    return () => media.removeListener(sync)
  }, [])

  useEffect(() => {
    if (!isMobile) setMobileSidebarOpen(false)
  }, [isMobile])

  const toggleSidebar = useCallback(() => {
    if (isMobile) {
      setMobileSidebarOpen(o => !o)
      return
    }
    setSidebarCollapsed(c => !c)
  }, [isMobile])

  const closeMobileSidebar = useCallback(() => setMobileSidebarOpen(false), [])

  return { isMobile, sidebarCollapsed, mobileSidebarOpen, toggleSidebar, closeMobileSidebar }
}
