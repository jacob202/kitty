'use client'

import { AlertCircle, ArrowDownToLine, Share2 } from 'lucide-react'
import type { PwaInstallState } from '@/lib/pwa'

interface Props {
  state: PwaInstallState
  error?: string | null
  installing?: boolean
  onInstall?: () => void
}

export function PwaInstallBanner({
  state,
  error = null,
  installing = false,
  onInstall,
}: Props) {
  if (state === 'hidden') return null

  if (state === 'error') {
    return (
      <div
        role="alert"
        style={{
          padding: '8px 16px',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--c-red)',
          background: 'rgba(255, 180, 171, 0.08)',
          borderBottom: '1px solid var(--line)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <AlertCircle size={14} style={{ flexShrink: 0 }} />
        <span>{error ?? 'install setup failed.'}</span>
      </div>
    )
  }

  return (
    <div
      role="status"
      style={{
        padding: '8px 16px',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--ink-2)',
        borderBottom: '1px solid var(--line)',
        background: 'rgba(26, 20, 16, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        flexShrink: 0,
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        {state === 'available' ? <ArrowDownToLine size={14} style={{ flexShrink: 0 }} /> : <Share2 size={14} style={{ flexShrink: 0 }} />}
        <span style={{ lineHeight: 1.5 }}>
          {state === 'available'
            ? 'Install Kitty for dock launch and a focused app window.'
            : 'on iPhone or iPad, install kitty from Safari with share → add to home screen.'}
        </span>
      </span>

      {state === 'available' && onInstall && (
        <button
          type="button"
          onClick={onInstall}
          disabled={installing}
          style={{
            border: 'none',
            borderRadius: 4,
            padding: '6px 10px',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            fontWeight: 700,
            cursor: installing ? 'default' : 'pointer',
            background: 'var(--surface)',
            color: 'var(--ink)',
            flexShrink: 0,
            opacity: installing ? 0.65 : 1,
          }}
        >
          {installing ? 'installing...' : 'install'}
        </button>
      )}
    </div>
  )
}
