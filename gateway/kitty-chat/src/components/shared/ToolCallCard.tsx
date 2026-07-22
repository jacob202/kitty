'use client'
import { useState, type ReactNode } from 'react'
import { Wrench, Check, X, Loader, ChevronDown, ChevronRight } from 'lucide-react'

export type ToolCallState = 'running' | 'done' | 'failed'

export interface ToolCall {
  name: string
  state: ToolCallState
  duration?: string
  error?: string
  children: ReactNode
}

const stateConfig: Record<ToolCallState, { icon: ReactNode; label: string; color: string }> = {
  running:  { icon: <Loader size={13} className="tool-call-spin" />, label: 'running',  color: 'var(--c-yellow)' },
  done:     { icon: <Check size={13} />,                    label: 'done',     color: 'var(--c-green)' },
  failed:   { icon: <X size={13} />,                        label: 'failed',   color: 'var(--c-red)' },
}

const ICON_SIZE = 13

export function ToolCallCard({ name, state, duration, error, children }: ToolCall) {
  const [expanded, setExpanded] = useState(state === 'running' || state === 'failed')
  const config = stateConfig[state]

  return (
    <div
      role="status"
      aria-label={`tool ${name}: ${config.label}`}
      style={{
        border: `1px solid ${state === 'running' ? 'var(--c-yellow)' : 'var(--line)'}`,
        borderRadius: 10,
        background: 'var(--surface-2)',
        marginTop: 10,
        marginBottom: 4,
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          color: 'var(--ink)',
          fontFamily: 'var(--font-body)',
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        <Wrench size={ICON_SIZE} style={{ color: 'var(--ink-2)', flexShrink: 0 }} />
        <span style={{ flex: 1, textAlign: 'left' }}>{name}</span>
        {duration && (
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--ink-2)',
          }}>
            {duration}
          </span>
        )}
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: config.color,
          fontFamily: 'var(--font-body)',
        }}>
          {config.icon}
          {config.label}
        </span>
        {expanded
          ? <ChevronDown size={ICON_SIZE} style={{ color: 'var(--ink-2)', flexShrink: 0 }} />
          : <ChevronRight size={ICON_SIZE} style={{ color: 'var(--ink-2)', flexShrink: 0 }} />
        }
      </button>
      {expanded && (
        <div style={{
          padding: '0 12px 10px 36px',
          fontSize: 13,
          color: 'var(--ink-2)',
          lineHeight: 1.55,
        }}>
          {children}
          {error && (
            <div style={{
              marginTop: 8,
              padding: '6px 10px',
              borderRadius: 6,
              background: 'rgba(217, 122, 102, 0.12)',
              color: 'var(--c-red)',
              fontSize: 12,
            }}>
              {error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const TOOL_PATTERNS = [
  /^\s*🔧\s*\*{0,2}([_a-zA-Z][_a-zA-Z0-9 ]*)/,
  /\[tool:(\w+)\]/,
  /<tool:(\w+)>/,
  /^#+\s*Tool:\s*(\w+)/im,
  /^\*{0,2}Tool\s+call:\s*\*{0,2}\s*(\w+)/im,
]

export function detectToolCalls(content: string): { toolName: string; blocks: string[] }[] {
  if (!content) return []

  const found: { toolName: string; blocks: string[] }[] = []
  const lines = content.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    let toolName: string | null = null

    for (const pattern of TOOL_PATTERNS) {
      const match = line.match(pattern)
      if (match?.[1]) {
        toolName = match[1].trim()
        break
      }
    }

    if (toolName) {
      i++
      const block: string[] = []
      while (i < lines.length) {
        const next = lines[i]
        if (TOOL_PATTERNS.some(p => p.test(next))) break
        if (/^\s*───/.test(next)) { i++; break }
        block.push(next)
        i++
      }
      found.push({ toolName, blocks: block })
    } else {
      i++
    }
  }

  return found
}

export function stripToolBlocks(content: string): string {
  if (!content) return content
  const lines = content.split('\n')
  const result: string[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const isTool = TOOL_PATTERNS.some(p => p.test(line))

    if (isTool) {
      i++
      while (i < lines.length) {
        const next = lines[i]
        if (TOOL_PATTERNS.some(p => p.test(next))) break
        if (/^\s*───/.test(next)) { i++; break }
        i++
      }
    } else {
      result.push(line)
      i++
    }
  }

  return result.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}
