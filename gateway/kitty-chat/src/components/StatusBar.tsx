'use client'

import { useRef, useState, type CSSProperties } from 'react'
import { AlertCircle, ArrowDownToLine, Share2, X } from 'lucide-react'
import type { AttachmentError } from '@/lib/attachment-validation'
import type { PwaInstallState } from '@/lib/pwa'

type SaveState = 'idle' | 'saving' | 'saved' | 'failed' | 'offline'

interface Props {
  /** Only relevant while a chat thread is on screen. */
  showChatSignals: boolean
  attachmentErrors: AttachmentError[]
  /** The model list could not be reached. NOT gateway reachability — HealthGate
   *  already proves the gateway is up before this component ever renders. */
  modelsUnavailable: boolean
  onRetryModels: () => void
  saveState: SaveState
  onRetrySave: () => void
  briefUnavailable: boolean
  briefError?: string | null
  pwaState: PwaInstallState
  pwaError?: string | null
  pwaInstalling?: boolean
  onPwaInstall?: () => void
}

const FAILS_REQUIRED = 3

/**
 * One line, ranked by how much it matters to the user right now. The old
 * layout stacked up to five independent banners (pwa install, models
 * unavailable, brief unavailable, save state, attachment errors) above the
 * thread; a user could see all five before a single message. Only the
 * highest-priority condition is ever visible — the rest wait their turn.
 */
export function StatusBar({
  showChatSignals,
  attachmentErrors,
  modelsUnavailable,
  onRetryModels,
  saveState,
  onRetrySave,
  briefUnavailable,
  briefError,
  pwaState,
  pwaError,
  pwaInstalling = false,
  onPwaInstall,
}: Props) {
  const unavailableStreakRef = useRef(0)
  const [pwaDismissed, setPwaDismissed] = useState(() => {
    if (typeof window === 'undefined') return false
    try {
      const stored = localStorage.getItem('kitty-pwa-install-dismissed')
      return stored === 'true'
    } catch {
      return false
    }
  })

  if (modelsUnavailable) {
    unavailableStreakRef.current++
  } else {
    unavailableStreakRef.current = 0
  }

  const confirmedUnavailable = unavailableStreakRef.current >= FAILS_REQUIRED

  if (showChatSignals && attachmentErrors.length > 0) {
    return (
      <div role="alert" style={{ ...rowStyle, color: 'var(--c-red)' }}>
        <AlertCircle size={14} style={{ flexShrink: 0 }} />
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {attachmentErrors.map((err, i) => (
            <span key={i}>{err.file}: {err.reason}</span>
          ))}
        </span>
      </div>
    )
  }

  if (confirmedUnavailable) {
    return (
      <div role="status" style={{ ...rowStyle, justifyContent: 'space-between' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={dotStyle} />
          Kitty can&apos;t reach any models right now.
        </span>
        <button type="button" onClick={onRetryModels} style={retryBtnStyle}>
          retry
        </button>
      </div>
    )
  }

  if (showChatSignals && (saveState === 'failed' || saveState === 'offline')) {
    return (
      <div role="status" style={{ ...rowStyle, color: 'var(--c-red)', justifyContent: 'space-between' }}>
        <span>
          {saveState === 'failed' ? 'save failed — chat not persisted' : 'offline — chat not saved'}
        </span>
        <button type="button" onClick={onRetrySave} style={retryBtnStyle}>
          retry
        </button>
      </div>
    )
  }

  if (briefUnavailable) {
    return (
      <div role="status" style={rowStyle}>
        Brief unavailable ({briefError ?? 'unknown'}). Chat still works.
      </div>
    )
  }

  if (pwaState === 'error') {
    return (
      <div role="alert" style={{ ...rowStyle, color: 'var(--c-red)' }}>
        <AlertCircle size={14} style={{ flexShrink: 0 }} />
        <span>{pwaError ?? 'install setup failed.'}</span>
      </div>
    )
  }

  if (pwaState === 'available' || pwaState === 'manual-ios') {
    if (pwaDismissed) return null
    return (
      <div role="status" style={{ ...rowStyle, justifyContent: 'space-between' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          {pwaState === 'available'
            ? <ArrowDownToLine size={14} style={{ flexShrink: 0 }} />
            : <Share2 size={14} style={{ flexShrink: 0 }} />}
          <span style={{ lineHeight: 1.5 }}>
            {pwaState === 'available'
              ? 'Install Kitty for dock launch and a focused app window.'
              : 'on iPhone or iPad, install kitty from Safari with share → add to home screen.'}
          </span>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          {pwaState === 'available' && onPwaInstall && (
            <button type="button" onClick={onPwaInstall} disabled={pwaInstalling} style={retryBtnStyle}>
              {pwaInstalling ? 'installing...' : 'install as app'}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              try {
                localStorage.setItem('kitty-pwa-install-dismissed', 'true')
              } catch {
                // storage failed, fall back to in-memory-only
              }
              setPwaDismissed(true)
            }}
            aria-label="Dismiss"
            style={closeBtnStyle}
          >
            <X size={12} />
          </button>
        </span>
      </div>
    )
  }

  if (showChatSignals && saveState === 'saving') {
    return <div role="status" style={rowStyle}>saving…</div>
  }

  if (showChatSignals && saveState === 'saved') {
    return <div role="status" style={rowStyle}>saved</div>
  }

  return null
}

const rowStyle: CSSProperties = {
  padding: '6px 16px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  borderBottom: '1px solid var(--line)',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  flexShrink: 0,
}

const dotStyle: CSSProperties = {
  width: 6,
  height: 6,
  borderRadius: '50%',
  background: 'var(--c-red)',
  flexShrink: 0,
  display: 'inline-block',
}

const retryBtnStyle: CSSProperties = {
  border: 'none',
  borderRadius: 4,
  padding: '2px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 600,
  cursor: 'pointer',
  background: 'transparent',
  color: 'inherit',
  flexShrink: 0,
}

const closeBtnStyle: CSSProperties = {
  border: 'none',
  borderRadius: 4,
  padding: 2,
  cursor: 'pointer',
  background: 'transparent',
  color: 'inherit',
  display: 'flex',
  alignItems: 'center',
  flexShrink: 0,
}
