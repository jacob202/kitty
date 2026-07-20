'use client'
import { useCallback, useEffect, useState } from 'react'

export type KittyTheme = 'cosmic' | 'day' | 'night'

export function useTheme() {
  const [theme, setTheme] = useState<KittyTheme>('cosmic')

  useEffect(() => {
    if (typeof window === 'undefined') return
    const saved = window.localStorage.getItem('kitty-theme')
    if (saved === 'cosmic' || saved === 'day' || saved === 'night') {
      setTheme(saved)
      document.documentElement.setAttribute('data-theme', saved)
    }
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(t => {
      const next = t === 'cosmic' ? 'day' : t === 'day' ? 'night' : 'cosmic'
      document.documentElement.setAttribute('data-theme', next)
      window.localStorage.setItem('kitty-theme', next)
      return next
    })
  }, [])

  return { theme, setTheme, toggleTheme }
}
