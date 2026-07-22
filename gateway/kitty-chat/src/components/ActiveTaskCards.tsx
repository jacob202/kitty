'use client'

import type { CSSProperties } from 'react'
import { useTasks } from '@/lib/queries'
import { useGatewayRuntimeManifest } from '@/lib/queries'
import type { GatewayTask, BuilderPacketStatus } from '@/lib/gateway'

interface ActiveItem {
  id: string
  label: string
  kind: 'task' | 'builder'
  state: string
  detail?: string
}

function gatewayTaskToItem(task: GatewayTask): ActiveItem {
  return {
    id: task.task_id,
    label: task.goal,
    kind: 'task',
    state: task.status,
  }
}

function builderPacketToItem(packet: BuilderPacketStatus): ActiveItem {
  const runState = packet.run?.state
  return {
    id: packet.packet_id,
    label: packet.title,
    kind: 'builder',
    state: runState ?? packet.task_state ?? 'queued',
    detail: packet.attempt_count > 0 ? `attempt ${packet.attempt_count}` : undefined,
  }
}

function isActiveTask(task: GatewayTask): boolean {
  return task.status === 'queued' || task.status === 'running'
}

function isActivePacket(packet: BuilderPacketStatus): boolean {
  const runState = packet.run?.state
  return runState === 'starting' || runState === 'running' || runState === 'cancel_requested'
    || packet.task_state === 'claimed' || packet.task_state === 'running'
}

export function ActiveTaskCards({ compact = false }: { compact?: boolean }) {
  const tasksQuery = useTasks(10)
  const runtimeQuery = useGatewayRuntimeManifest()

  const gatewayItems = (tasksQuery.data ?? [])
    .filter(isActiveTask)
    .map(gatewayTaskToItem)

  const builderItems = (runtimeQuery.data?.execution.builder?.value?.initiatives ?? [])
    .flatMap((i) => i.packets)
    .filter(isActivePacket)
    .map(builderPacketToItem)

  const items = [...builderItems, ...gatewayItems]

  if (items.length === 0) return null

  return (
    <div style={compact ? compactWrapStyle : wrapStyle} role="status" aria-label="Active tasks">
      {items.map((item) => (
        <div key={item.id} style={compact ? compactCardStyle : cardStyle}>
          <span style={dotStyle(item.state)} />
          <span style={kindStyle(item.kind)}>{item.kind === 'builder' ? 'build' : item.kind}</span>
          <span style={labelStyle}>{item.label}</span>
          <span style={stateStyle}>{item.state.replace(/_/g, ' ')}</span>
          {item.detail && <span style={detailStyle}>{item.detail}</span>}
        </div>
      ))}
    </div>
  )
}

const STATE_COLORS: Record<string, string> = {
  running: 'var(--cat-ginger)',
  starting: 'var(--c-yellow)',
  queued: 'var(--ink-2)',
  claimed: 'var(--c-blue)',
  cancel_requested: 'var(--c-red)',
}

function dotStyle(state: string): CSSProperties {
  const color = STATE_COLORS[state] ?? 'var(--ink-2)'
  const isActive = state === 'running' || state === 'starting'
  return {
    width: 5,
    height: 5,
    borderRadius: 99,
    background: color,
    flexShrink: 0,
    ...(isActive ? { animation: 'pulse 1.4s ease-in-out infinite' } : {}),
  }
}

const wrapStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  padding: '6px 0',
}

const compactWrapStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 3,
  padding: '4px 0',
}

const cardStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '5px 8px',
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 6,
  minWidth: 0,
}

const compactCardStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 5,
  padding: '4px 7px',
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 5,
  minWidth: 0,
}

function kindStyle(kind: 'task' | 'builder'): CSSProperties {
  return {
    fontFamily: 'var(--font-mono)',
    fontSize: 9,
    fontWeight: 700,
    color: kind === 'builder' ? 'var(--cat-ginger)' : 'var(--c-purple)',
    letterSpacing: '0.06em',
    flexShrink: 0,
  }
}

const labelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  flex: 1,
  minWidth: 0,
}

const stateStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--ink-2)',
  flexShrink: 0,
}

const detailStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--ink-2)',
  opacity: 0.7,
  flexShrink: 0,
}
