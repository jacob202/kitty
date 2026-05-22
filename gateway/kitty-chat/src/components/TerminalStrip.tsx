'use client'
import { useState, useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'

interface LogEntry {
  timestamp: Date
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
}

interface Props {
  title?: string
  maxLines?: number
}

export function TerminalStrip({ title = 'terminal', maxLines = 50 }: Props) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const interval = setInterval(() => {
      const levels: LogEntry['level'][] = ['info', 'warn', 'error', 'debug']
      const sampleMessages = [
        'Gateway heartbeat received',
        'Search index updated',
        'New todo created',
        'Loop execution completed',
        'Brief generation started',
        'Agent task finished',
        'Insight detected',
        'Memory consolidation complete',
        'Model response streamed',
      ]
      const newLog: LogEntry = {
        timestamp: new Date(),
        level: levels[Math.floor(Math.random() * levels.length)],
        message: sampleMessages[Math.floor(Math.random() * sampleMessages.length)],
      }
      setLogs(prev => [...prev.slice(-maxLines + 1), newLog])
    }, 3000)

    return () => clearInterval(interval)
  }, [maxLines])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const levelColor = (level: LogEntry['level']): string => {
    switch (level) {
      case 'error': return 'var(--error)'
      case 'warn': return 'var(--orange)'
      case 'debug': return 'var(--text-muted)'
      default: return 'var(--mint)'
    }
  }

  const formatTime = (ts: Date): string => {
    return ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>{title}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
          {logs.length} lines
        </span>
      </div>
      <div style={terminalStyle}>
        {logs.map((log, i) => (
          <div key={i} style={lineStyle}>
            <span style={timeStyle}>{formatTime(log.timestamp)}</span>
            <span style={{ ...levelBadgeStyle, color: levelColor(log.level), borderColor: levelColor(log.level) }}>
              {log.level.toUpperCase()}
            </span>
            <span style={messageStyle}>{log.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
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
  borderBottom: '1px solid var(--border-dim)',
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--text)',
}

const terminalStyle: CSSProperties = {
  flex: 1,
  background: 'var(--panel)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '12px',
  overflowY: 'auto',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  lineHeight: 1.6,
}

const lineStyle: CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  whiteSpace: 'nowrap',
}

const timeStyle: CSSProperties = {
  color: 'var(--text-muted)',
  flexShrink: 0,
}

const levelBadgeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  border: '1px solid',
  borderRadius: 4,
  padding: '1px 4px',
  background: 'transparent',
  flexShrink: 0,
}

const messageStyle: CSSProperties = {
  color: 'var(--text)',
  flexShrink: 0,
}
