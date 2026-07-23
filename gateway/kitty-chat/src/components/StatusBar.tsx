'use client'

import { useRef, type CSSProperties } from 'react'
import { AlertCircle, ArrowDownToLine, Share2 } from 'lucide-react'
import type { AttachmentError } from '@/lib/attachment-validation'
import type { PwaInstallState } from '@/lib/pwa'

type SaveState = 'idle' | 'saving' | 'saved' | 'failed' | 'offline'

interface Props {
  /** Only relevant while a chat thread is on screen. */
  showChatSignals: boolean
  attachmentErrors: AttachmentError[]
  gatewayOffline: boolean
  onRetryGateway: () => void
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
 * layout stacked up to five independent banners (pwa install, gateway
 * offline, brief unavailable, save state, attachment errors) above the
 * thread; a user could see all five before a single message. Only the
 * highest-priority condition is ever visible — the rest wait their turn.
 */
export function StatusBar({
  showChatSignals,
  attachmentErrors,
  gatewayOffline,
  onRetryGateway,
  saveState,
  onRetrySave,
  briefUnavailable,
  briefError,
  pwaState,
  pwaError,
  pwaInstalling = false,
  onPwaInstall,
}: Props) {
  const offlineStreakRef = useRef(0)

  if (gatewayOffline) {
    offlineStreakRef.current++
  } else {
    offlineStreakRef.current = 0
  }

  const confirmedOffline = offlineStreakRef.current >= FAILS_REQUIRED

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

  if (confirmedOffline) {
    return (
      <div role="status" style={{ ...rowStyle, justifyContent: 'space-between' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={dotStyle} />
          gateway offline
        </span>
        <button type="button" onClick={onRetryGateway} style={retryBtnStyle}>
          retry
        </button>
      </div>
    )
  }

  if (showChatSignals && (saveState === 'failed' || saveState === 'offline')) {
    return (
      <div role="status" style={{ ...rowStyle, color: 'var(--c-red)', justifyContent: 'space-between' }}>
        <span>
          {saveState === 'failed' ? 'save failed — chat not persisted' : 'gateway offline — chat not saved'}
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
        {pwaState === 'available' && onPwaInstall && (
          <button type="button" onClick={onPwaInstall} disabled={pwaInstalling} style={retryBtnStyle}>
            {pwaInstalling ? 'installing...' : 'install'}
          </button>
        )}
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
