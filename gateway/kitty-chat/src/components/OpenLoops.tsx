'use client'
import type { CSSProperties } from 'react'
import { card, sectionLabel } from '@/lib/ui'

interface Props {
  untriagedCount: number
  proposedCount: number
  needsJacobCount: number
  triageBusy?: boolean
  onRunTriage: () => void
  onJumpToNeedsYou: () => void
}

export function OpenLoops({
  untriagedCount,
  proposedCount,
  needsJacobCount,
  triageBusy = false,
  onRunTriage,
  onJumpToNeedsYou,
}: Props) {
  return (
    <div style={containerStyle}>
      <span style={labelStyle}>open loops</span>
      <button type="button" onClick={onRunTriage} disabled={triageBusy || untriagedCount === 0} style={pillStyle}>
        {untriagedCount} untriaged · triage now
      </button>
      <button type="button" onClick={onJumpToNeedsYou} disabled={proposedCount === 0} style={pillStyle}>
        {proposedCount} proposed action{proposedCount === 1 ? '' : 's'}
      </button>
      <button type="button" onClick={onJumpToNeedsYou} disabled={needsJacobCount === 0} style={pillStyle}>
        {needsJacobCount} need{needsJacobCount === 1 ? 's' : ''} a decision
      </button>
    </div>
  )
}

const containerStyle: CSSProperties = {
  ...card,
  display: 'flex',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: 8,
  padding: '10px 16px',
}

const labelStyle: CSSProperties = { ...sectionLabel, marginRight: 4 }

const pillStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  border: '1px solid var(--border)',
  borderRadius: 999,
  padding: '4px 10px',
  background: 'var(--surface-mid)',
  cursor: 'pointer',
}
