'use client'
import { useState, useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'

import { fetchLogTail } from '../lib/gateway'

interface Props {
  title?: string
  maxLines?: number
  file?: string
  pollMs?: number
}

type Level = 'info' | 'warn' | 'error' | 'debug'

function lineLevel(line: string): Level {
  if (/error|traceback|critical/i.test(line)) return 'error'
  if (/warn/i.test(line)) return 'warn'
  if (/debug/i.test(line)) return 'debug'
  return 'info'
}

export function TerminalStrip({ title = 'gateway log', maxLines = 100, file = 'gateway', pollMs = 5000 }: Props) {
  const [lines, setLines] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const payload = await fetchLogTail(file, maxLines)
        if (!cancelled) {
          setLines(payload.lines)
          setError(null)
        }
      } catch {
        if (!cancelled) setError('log unavailable. is the gateway up?')
      }
    }
    void load()
    const interval = setInterval(() => { void load() }, pollMs)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [file, maxLines, pollMs])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const levelColor = (level: Level): string => {
    switch (level) {
      case 'error': return 'var(--c-red)'
      case 'warn': return 'var(--cat-ginger)'
      case 'debug': return 'var(--ink-2)'
      default: return 'var(--ink)'
    }
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>{title}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
          {lines.length} lines
        </span>
      </div>
      <div style={terminalStyle}>
        {error ? (
          <div style={{ color: 'var(--ink-2)' }}>{error}</div>
        ) : lines.length === 0 ? (
          <div style={{ color: 'var(--ink-2)' }}>nothing logged yet</div>
        ) : (
          lines.map((line, i) => (
            <div key={i} style={{ ...lineStyle, color: levelColor(lineLevel(line)) }}>
              {line}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  height: '400px',
}

const headerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingBottom: 8,
  borderBottom: '1px solid var(--line)',
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--ink)',
}

const terminalStyle: CSSProperties = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '12px',
  overflowY: 'auto',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  lineHeight: 1.6,
}

const lineStyle: CSSProperties = {
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
}
