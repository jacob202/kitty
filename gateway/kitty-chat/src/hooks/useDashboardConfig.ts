'use client'

import { useCallback, useEffect, useState } from 'react'

export interface UseDashboardConfigResult {
  visibleTiles: Record<string, boolean>
  toggleTile: (tileId: string) => void
  resetToDefaults: () => void
}

const STORAGE_KEY = 'kitty-dashboard-config'

export function useDashboardConfig(): UseDashboardConfigResult {
  const [visibleTiles, setVisibleTiles] = useState<Record<string, boolean>>(defaultTiles)

  // localStorage isn't available during SSR — render the defaults first,
  // then sync the real preference in once we're mounted on the client.
  useEffect(() => {
    setVisibleTiles(readStoredTiles())
  }, [])

  const toggleTile = useCallback((tileId: string) => {
    const next = { ...visibleTiles, [tileId]: !visibleTiles[tileId] }
    setVisibleTiles(next)
    writeStoredTiles(next)
  }, [visibleTiles])

  const resetToDefaults = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEY)
    }
    setVisibleTiles(defaultTiles())
  }, [])

  return { visibleTiles, toggleTile, resetToDefaults }
}

function defaultTiles(): Record<string, boolean> {
  return {
    'whats-next': true,
    'needs-you': true,
    deadlines: true,
    'active-projects': true,
    'what-changed': true,
    today: true,
    health: true,
    capture: true,
  }
}

function readStoredTiles(): Record<string, boolean> {
  if (typeof window === 'undefined') return defaultTiles()

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultTiles()
    // Merge over defaults so a tile added after a preference was saved still starts visible.
    return { ...defaultTiles(), ...JSON.parse(raw) }
  } catch {
    return defaultTiles()
  }
}

function writeStoredTiles(tiles: Record<string, boolean>): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tiles))
}
