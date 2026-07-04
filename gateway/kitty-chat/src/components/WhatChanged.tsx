'use client'
import type { CSSProperties } from 'react'
import type { GatewayStateChange, GatewaySignal } from '@/lib/gateway'
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState } from '@/lib/ui'
import { Skeleton } from './Skeleton'

interface Props {
  changes: GatewayStateChange[]
  newSignals: GatewaySignal[]
  note?: string
  hasBaseline: boolean
  isLoading?: boolean
  error: string | null
  onSnapshot: () => void
  snapshotBusy?: boolean
}

function formatChange(change: GatewayStateChange): string {
  return `${change.section}.${change.field}: ${String(change.before)} → ${String(change.after)}`
}

function formatSignal(signal: GatewaySignal): string {
  return `${signal.kind} · ${signal.source}`
}

export function WhatChanged({
  changes,
  newSignals,
  note,
  hasBaseline,
  isLoading = false,
  error,
  onSnapshot,
  snapshotBusy = false,
}: Props) {
  const total = changes.length + newSignals.length

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>What changed</span>
        <button type="button" onClick={onSnapshot} disabled={snapshotBusy} style={snapshotBtnStyle}>
          {hasBaseline ? 'mark point' : 'start tracking'}
        </button>
      </div>

      {error ? (
        <div style={errorStyle} role="alert">Can&apos;t reach the gateway ({error}).</div>
      ) : isLoading && total === 0 ? (
        <div style={{ display: 'grid', gap: 8 }}>
          <Skeleton height={40} />
          <Skeleton height={40} />
        </div>
      ) : !hasBaseline ? (
        <div style={emptyStyle}>{note ?? 'No baseline yet — click "start tracking" to set one.'}</div>
      ) : total === 0 ? (
        <div style={emptyStyle}>No changes since the last snapshot.</div>
      ) : (
        <div style={listStyle}>
          {changes.map((change, i) => (
            <div key={`change-${i}`} style={itemStyle}>{formatChange(change)}</div>
          ))}
          {newSignals.map((signal) => (
            <div key={`signal-${signal.id}`} style={itemStyle}>{formatSignal(signal)}</div>
          ))}
        </div>
      )}
    </div>
  )
}

const containerStyle: CSSProperties = { ...card, display: 'flex', flexDirection: 'column', gap: 12 }
const headerStyle: CSSProperties = cardHeader
const titleStyle: CSSProperties = cardTitle

const snapshotBtnStyle: CSSProperties = {
  ...cardMeta,
  border: '1px solid var(--border)',
  borderRadius: 4,
  padding: '3px 8px',
  cursor: 'pointer',
  background: 'var(--surface-mid)',
}

const listStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6 }

const itemStyle: CSSProperties = {
  ...itemCard,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  padding: '8px 10px',
}

const errorStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--error)',
  padding: '8px 0',
}

const emptyStyle: CSSProperties = emptyState
