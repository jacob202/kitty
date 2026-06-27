'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

declare global {
  interface WindowEventMap {
    beforeinstallprompt: BeforeInstallPromptEvent
    appinstalled: Event
  }

  interface Navigator {
    standalone?: boolean
  }
}

export type PwaInstallState = 'hidden' | 'available' | 'manual-ios' | 'error'

export interface UsePwaInstallResult {
  state: PwaInstallState
  error: string | null
  installing: boolean
  install: () => Promise<void>
}

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function isStandaloneDisplayMode(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true
}

function isIosSafari(): boolean {
  if (typeof window === 'undefined') return false

  const { userAgent, platform, maxTouchPoints } = window.navigator
  const isiPhoneOrIPad =
    /iPad|iPhone|iPod/.test(userAgent) ||
    (platform === 'MacIntel' && maxTouchPoints > 1)
  const isSafari = /Safari/i.test(userAgent) && !/CriOS|FxiOS|EdgiOS/i.test(userAgent)

  return isiPhoneOrIPad && isSafari
}

export function usePwaInstall(): UsePwaInstallResult {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [installing, setInstalling] = useState(false)
  const [isInstalled, setIsInstalled] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return

    let cancelled = false
    const media = window.matchMedia('(display-mode: standalone)')

    const syncInstalledState = () => {
      if (!cancelled) {
        setIsInstalled(isStandaloneDisplayMode())
      }
    }

    syncInstalledState()

    const handleBeforeInstallPrompt = (event: BeforeInstallPromptEvent) => {
      event.preventDefault()
      if (cancelled) return
      setInstallPrompt(event)
      setError(null)
    }

    const handleAppInstalled = () => {
      if (cancelled) return
      setIsInstalled(true)
      setInstallPrompt(null)
      setError(null)
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', syncInstalledState)
    } else {
      media.addListener(syncInstalledState)
    }

    if (!('serviceWorker' in window.navigator)) {
      setError('This browser does not support service workers, so Kitty cannot be installed here.')
    } else {
      void window.navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then(() => {
          if (!cancelled) {
            setError(null)
          }
        })
        .catch(registrationError => {
          if (!cancelled) {
            setError(`Service worker registration failed: ${messageFromError(registrationError)}`)
          }
        })
    }

    return () => {
      cancelled = true
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleAppInstalled)
      if (typeof media.removeEventListener === 'function') {
        media.removeEventListener('change', syncInstalledState)
      } else {
        media.removeListener(syncInstalledState)
      }
    }
  }, [])

  const install = useCallback(async () => {
    if (!installPrompt) {
      throw new Error('Kitty install prompt is not available in this browser session.')
    }

    setInstalling(true)
    try {
      await installPrompt.prompt()
      const choice = await installPrompt.userChoice
      setInstallPrompt(null)
      if (choice.outcome === 'accepted') {
        setIsInstalled(true)
      }
    } catch (installError) {
      const message = `Install prompt failed: ${messageFromError(installError)}`
      setError(message)
      throw new Error(message)
    } finally {
      setInstalling(false)
    }
  }, [installPrompt])

  const state = useMemo<PwaInstallState>(() => {
    if (isInstalled) return 'hidden'
    if (error) return 'error'
    if (installPrompt) return 'available'
    if (isIosSafari()) return 'manual-ios'
    return 'hidden'
  }, [error, installPrompt, isInstalled])

  return { state, error, installing, install }
}
