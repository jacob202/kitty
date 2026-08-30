'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { CatState } from '@/components/CrayonCat'

interface UseKittyStateOptions {
  isStreaming: boolean
  lastError: boolean
  builderActive: boolean
  doneWindowMs?: number
}

export function useKittyState({
  isStreaming,
  lastError,
  builderActive,
  doneWindowMs = 5000,
}: UseKittyStateOptions): CatState {
  const [state, setState] = useState<CatState>('idle')
  const prevStreaming = useRef(isStreaming)
  const doneTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const justFinished = useRef(false)

  const derive = useCallback(() => {
    if (isStreaming || builderActive) return 'working'
    if (lastError) return 'broke'
    if (justFinished.current) return 'done'
    return 'idle'
  }, [isStreaming, lastError, builderActive])

  useEffect(() => {
    // Streaming stopped → trigger done state temporarily
    if (prevStreaming.current && !isStreaming) {
      justFinished.current = true
      setState('done')

      doneTimer.current = setTimeout(() => {
        justFinished.current = false
        setState(derive())
        doneTimer.current = null
      }, doneWindowMs)
    } else {
      setState(derive())
    }

    prevStreaming.current = isStreaming

    return () => {
      if (doneTimer.current) clearTimeout(doneTimer.current)
    }
  }, [derive, isStreaming, doneWindowMs])

  return state
}

// Guard: these two combinations must never occur in the same render frame.
// Encode as a test, not a runtime check.
export const FORBIDDEN = {
  doneWhileRunning: `State 'done' must never coexist with isStreaming=true or builderActive=true`,
  workingAtIdle: `State 'working' must never coexist with isStreaming=false and builderActive=false without a pending operation`,
} as const
