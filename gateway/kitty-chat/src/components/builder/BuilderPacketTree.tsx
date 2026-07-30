'use client'

import type { CSSProperties } from 'react'
import type { BuilderStatusSnapshot, BuilderInitiativeStatus, BuilderPacketStatus } from '@/lib/gateway'

const treeRoot: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  overflow: 'auto',
}

const initiativeHeader: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '8px 12px',
  borderBottom: '1px solid var(--line)',
  cursor: 'pointer',
  userSelect: 'none',
}

const initiativeTitle: CSSProperties = {
  fontWeight: 700,
  color: 'var(--ink)',
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const packetRow: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '6px 12px 6px 28px',
  borderBottom: '1px solid var(--line)',
  cursor: 'pointer',
}

const packetRowSelected: CSSProperties = {
  ...packetRow,
  background: 'var(--surface-2)',
}

const packetTitle: CSSProperties = {
  color: 'var(--ink)',
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const dot: CSSProperties = {
  width: 7,
  height: 7,
  borderRadius: '50%',
  flexShrink: 0,
}

const badge: CSSProperties = {
  padding: '1px 5px',
  borderRadius: 3,
  fontSize: 9,
  fontWeight: 600,
  flexShrink: 0,
}

function stateLabel(packet: BuilderPacketStatus): { label: string; color: string } {
  const run = packet.run
  if (run?.state === 'running') return { label: 'running', color: '#4CAF50' }
  if (packet.task_state === 'blocked' || packet.blocked_reason) return { label: 'blocked', color: '#FF9800' }
  if (packet.task_state === 'failed') return { label: 'failed', color: '#F44336' }
  if (packet.task_state === 'done') return { label: 'done', color: '#2196F3' }
  if (packet.task_state === 'review-ready' || packet.task_state === 'awaiting_review') return { label: 'review', color: '#9C27B0' }
  if (packet.task_state === 'cancelled') return { label: 'cancelled', color: '#757575' }
  if (packet.task_state === 'claimed') return { label: 'claimed', color: '#8BC34A' }
  if (packet.run) return { label: 'queued', color: '#607D8B' }
  return { label: 'not queued', color: 'var(--ink-3)' }
}

function ellipsis(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '…' : s
}

interface BuilderPacketTreeProps {
  snapshot: BuilderStatusSnapshot
  selected?: { initiativeId: string; packetId: string } | null
  onSelect: (initiativeId: string, packetId: string) => void
}

export function BuilderPacketTree({ snapshot, selected, onSelect }: BuilderPacketTreeProps) {
  if (!snapshot || !snapshot.initiatives?.length) {
    return (
      <div style={{ padding: 12, fontSize: 12, color: 'var(--ink-3)' }}>
        No initiatives in snapshot.
      </div>
    )
  }

  return (
    <div style={treeRoot}>
      {snapshot.initiatives.map((initiative) => (
        <PacketsForInitiative
          key={initiative.initiative_id}
          initiative={initiative}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

function PacketsForInitiative({
  initiative,
  selected,
  onSelect,
}: {
  initiative: BuilderInitiativeStatus
  selected?: { initiativeId: string; packetId: string } | null
  onSelect: (initiativeId: string, packetId: string) => void
}) {
  return (
    <div>
      <div style={initiativeHeader}>
        <span style={{ fontSize: 10, color: 'var(--ink-2)' }}>
          {initiative.title.slice(0, 30)}
        </span>
        <span style={{ color: 'var(--ink-3)', fontSize: 9 }}>
          {initiative.packets?.length ?? 0}
        </span>
      </div>
      {(initiative.packets ?? []).map((packet) => {
        const isSelected = selected?.initiativeId === initiative.initiative_id
          && selected?.packetId === packet.packet_id
        const sl = stateLabel(packet)
        return (
          <div
            key={packet.packet_id}
            style={isSelected ? packetRowSelected : packetRow}
            onClick={() => onSelect(initiative.initiative_id, packet.packet_id)}
            role="option"
            aria-selected={isSelected}
          >
            <span style={{ ...dot, background: sl.color }} />
            <span style={packetTitle}>
              {ellipsis(packet.title || packet.packet_id, 40)}
            </span>
            <span style={{ ...badge, color: sl.color, background: sl.color + '18' }}>
              {sl.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
