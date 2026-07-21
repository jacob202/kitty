'use client'
import { useState } from 'react'
import type { CSSProperties } from 'react'
import type { ToolCall } from '@/lib/types'

interface Props {
  toolCall: ToolCall
  isStreaming?: boolean
}

function formatArgs(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

export function ToolCallBlock({ toolCall, isStreaming = false }: Props) {
  const [open, setOpen] = useState(false)
  const hasArgs = toolCall.arguments.length > 0 && toolCall.arguments !== '{}'

  return (
    <div style={wrapStyle}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={headerStyle}
        aria-expanded={open}
      >
        <span style={dotStyle(isStreaming)} />
        <span style={nameStyle}>{toolCall.name || 'tool call'}</span>
        {hasArgs && <span style={chevronStyle}>{open ? '▾' : '▸'}</span>}
      </button>
      {open && hasArgs && (
        <pre style={argsStyle}>{formatArgs(toolCall.arguments)}</pre>
      )}
    </div>
  )
}

export function ToolCallList({ toolCalls, isStreaming = false }: { toolCalls: ToolCall[]; isStreaming?: boolean }) {
  if (!toolCalls.length) return null
  return (
    <div style={listStyle}>
      {toolCalls.map((tc) => (
        <ToolCallBlock key={tc.id || tc.name} toolCall={tc} isStreaming={isStreaming} />
      ))}
    </div>
  )
}

const listStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  margin: '6px 0',
}

const wrapStyle: CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: 6,
  overflow: 'hidden',
}

const headerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  width: '100%',
  padding: '5px 8px',
  background: 'var(--surface-2)',
  border: 'none',
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  textAlign: 'left',
}

function dotStyle(streaming: boolean): CSSProperties {
  return {
    width: 6,
    height: 6,
    borderRadius: 99,
    background: streaming ? 'var(--c-yellow)' : 'var(--c-green)',
    flexShrink: 0,
    ...(streaming ? { animation: 'pulse 1.4s ease-in-out infinite' } : {}),
  }
}

const nameStyle: CSSProperties = {
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const chevronStyle: CSSProperties = {
  fontSize: 9,
  color: 'var(--ink-2)',
  flexShrink: 0,
}

const argsStyle: CSSProperties = {
  margin: 0,
  padding: '6px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 10.5,
  lineHeight: 1.5,
  color: 'var(--ink-2)',
  overflowX: 'auto',
  borderTop: '1px solid var(--line)',
}
