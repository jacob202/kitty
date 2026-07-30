'use client'

import { useEffect, useRef, type CSSProperties } from 'react'
import { useLiveBuilderEvents, type BuilderLiveEvent } from './useLiveBuilderEvents'
import type { BuilderPacketStatus } from '@/lib/gateway'

const logContainer: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  lineHeight: '1.5',
  overflow: 'auto',
  padding: 12,
  height: '100%',
  boxSizing: 'border-box',
}

const logLine: CSSProperties = {
  padding: '2px 0',
  borderBottom: '1px solid var(--line)',
  wordBreak: 'break-all',
}

const eventTypeStyle: CSSProperties = {
  fontSize: 9,
  fontWeight: 700,
  marginRight: 6,
  flexShrink: 0,
}

const timestampStyle: CSSProperties = {
  fontSize: 9,
  color: 'var(--ink-3)',
  marginRight: 6,
  flexShrink: 0,
}

function eventColor(type: string): string {
  switch (type) {
    case 'text_delta': return '#4CAF50'
    case 'message_complete': return '#2196F3'
    case 'tool_start': case 'tool_end': return '#FF9800'
    case 'command_start': case 'command_end': return '#9C27B0'
    case 'error': return '#F44336'
    case 'cancelled': return '#757575'
    case 'session_started': case 'session_resumed': return '#8BC34A'
    case 'attention_request': return '#FF5722'
    default: return 'var(--ink-2)'
  }
}

function eventLabel(type: string): string {
  return type.replace(/_/g, ' ')
}

function eventPayloadSummary(event: BuilderLiveEvent): string {
  const p = event.payload ?? {}
  if (typeof (p as { line?: string }).line === 'string') return (p as { line: string }).line
  if (typeof (p as { text?: string }).text === 'string') return (p as { text: string }).text
  if (typeof (p as { summary?: string }).summary === 'string') return (p as { summary: string }).summary
  if (typeof (p as { reason?: string }).reason === 'string') return (p as { reason: string }).reason
  if (typeof (p as { tool?: string }).tool === 'string') return `tool: ${(p as { tool: string }).tool}`
  if (typeof (p as { command?: string }).command === 'string') return `$ ${(p as { command: string }).command}`
  return JSON.stringify(p).slice(0, 120)
}

interface WorkerPaneProps {
  packet: BuilderPacketStatus | null
}

export function WorkerPane({ packet }: WorkerPaneProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const { events, connected } = useLiveBuilderEvents({
    packetId: packet?.packet_id,
    enabled: !!packet,
  })

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events.length])

  if (!packet) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>
          Select a packet from the tree to view its live events.
        </p>
      </div>
    )
  }

  const run = packet.run

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--line)',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
      }}>
        <span style={{ fontWeight: 700, color: 'var(--ink)' }}>
          {packet.title || packet.packet_id}
        </span>
        <span style={{
          fontSize: 9,
          color: connected ? '#4CAF50' : 'var(--ink-3)',
        }}>
          {connected ? 'live' : run ? 'disconnected' : 'no run'}
        </span>
      </div>

      {run && (
        <div style={{
          display: 'flex',
          gap: 12,
          padding: '6px 12px',
          borderBottom: '1px solid var(--line)',
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--ink-2)',
        }}>
          <span>state: {run.state}</span>
          {run.exit_code !== null && <span>exit: {run.exit_code}</span>}
          {run.started_at && <span>started: {new Date(run.started_at).toLocaleTimeString()}</span>}
        </div>
      )}

      <div ref={scrollRef} style={logContainer}>
        {!connected && events.length === 0 && (
          <p style={{ fontSize: 12, color: 'var(--ink-3)', margin: '24px 0', textAlign: 'center' }}>
            {run ? 'Connecting to event stream…' : 'No active run for this packet.'}
          </p>
        )}

        {events.map((event) => (
          <div key={event.event_id} style={logLine}>
            <span style={{ ...eventTypeStyle, color: eventColor(event.type) }}>
              {eventLabel(event.type)}
            </span>
            <span style={timestampStyle}>
              {new Date(event.timestamp).toLocaleTimeString()}
            </span>
            <span style={{ color: 'var(--ink)' }}>
              {eventPayloadSummary(event)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
