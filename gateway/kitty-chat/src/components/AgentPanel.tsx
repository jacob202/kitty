'use client'
import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import {
  fetchAgentSessions, spawnAgent, stopAgent,
  fetchAgentStatus, type AgentSession, type AgentType,
} from '@/lib/gateway'

const AGENT_TYPES: { id: AgentType; label: string; desc: string }[] = [
  { id: 'explorer',   label: 'explore',  desc: 'Wide research & discovery' },
  { id: 'planner',    label: 'plan',     desc: 'Break goal into steps' },
  { id: 'coder',      label: 'code',     desc: 'Analyze & implement' },
  { id: 'reviewer',   label: 'review',   desc: 'Find issues & suggestions' },
  { id: 'researcher', label: 'research', desc: 'Deep technical research' },
]

export function AgentPanel() {
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [goal, setGoal] = useState('')
  const [agentType, setAgentType] = useState<AgentType>('explorer')
  const [spawning, setSpawning] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    void load()
    const id = setInterval(() => void load(), 4000)
    return () => clearInterval(id)
  }, [])

  async function load() {
    setSessions(await fetchAgentSessions(8))
  }

  async function handleSpawn() {
    const g = goal.trim()
    if (!g || spawning) return
    setSpawning(true)
    const sid = await spawnAgent(g, agentType)
    setSpawning(false)
    if (sid) {
      setGoal('')
      await load()
    }
  }

  async function handleStop(sid: number) {
    await stopAgent(sid)
    await load()
  }

  async function handleExpand(sid: number) {
    if (expanded === sid) { setExpanded(null); return }
    const status = await fetchAgentStatus(sid)
    if (status) {
      setSessions(prev => prev.map(s => s.session_id === sid ? { ...s, ...status } : s))
    }
    setExpanded(sid)
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {/* Type selector */}
      <div style={typeRowStyle}>
        {AGENT_TYPES.map(t => (
          <button
            key={t.id}
            onClick={() => setAgentType(t.id)}
            title={t.desc}
            style={{
              ...typeChipStyle,
              background: agentType === t.id ? 'rgba(102,119,204,0.18)' : 'transparent',
              color: agentType === t.id ? 'var(--indigo)' : 'var(--text-muted)',
              borderColor: agentType === t.id ? 'rgba(102,119,204,0.4)' : 'var(--border-dim)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Goal input */}
      <div style={{ display: 'flex', gap: 5 }}>
        <input
          value={goal}
          onChange={e => setGoal(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && void handleSpawn()}
          placeholder="goal for the agent…"
          style={inputStyle}
        />
        <button
          onClick={() => void handleSpawn()}
          disabled={!goal.trim() || spawning}
          style={{ ...spawnBtnStyle, opacity: !goal.trim() || spawning ? 0.4 : 1 }}
        >
          {spawning ? '…' : 'Run'}
        </button>
      </div>

      {/* Session list */}
      {sessions.length > 0 ? (
        <div style={{ display: 'grid', gap: 4 }}>
          {sessions.map(s => (
            <div key={s.session_id} style={sessionRowStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <button onClick={() => void handleExpand(s.session_id)} style={goalBtnStyle}>
                  <span style={goalTextStyle}>{s.goal.slice(0, 55)}{s.goal.length > 55 ? '…' : ''}</span>
                </button>
                <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
                  {(s.status === 'running' || s.status === 'queued') && (
                    <button onClick={() => void handleStop(s.session_id)} style={stopBtnStyle} title="stop">Stop</button>
                  )}
                  <span style={statusBadgeStyle(s.status)}>{s.status}</span>
                </div>
              </div>

              {expanded === s.session_id && (
                <div style={outputBoxStyle}>
                  {s.iterations != null && (
                    <p style={metaLineStyle}>{s.iterations} iteration{s.iterations !== 1 ? 's' : ''} · {s.total_steps ?? 0} steps</p>
                  )}
                  {s.output ? (
                    <p style={outputTextStyle}>{s.output.slice(0, 600)}{s.output.length > 600 ? '…' : ''}</p>
                  ) : s.last_output_snippet ? (
                    <p style={outputTextStyle}>{s.last_output_snippet}</p>
                  ) : (
                    <p style={outputTextStyle}>No output yet.</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p style={emptyStyle}>no agents yet</p>
      )}
    </div>
  )
}

function statusBadgeStyle(status: string): CSSProperties {
  const color = status === 'running' ? 'var(--teal)'
    : status === 'completed' ? 'var(--text-muted)'
    : status === 'failed' ? 'var(--orange)'
    : 'var(--text-faint)'
  return { fontFamily: 'var(--font-mono)', fontSize: 9, color, textTransform: 'uppercase', letterSpacing: '0.06em' }
}

const typeRowStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

const typeChipStyle: CSSProperties = {
  padding: '3px 8px',
  border: '1px solid var(--border-dim)',
  borderRadius: 12,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  cursor: 'pointer',
}

const inputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  padding: '5px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
  minWidth: 0,
}

const spawnBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'rgba(102,119,204,0.12)',
  border: '1px solid rgba(102,119,204,0.3)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--indigo)',
  cursor: 'pointer',
  flexShrink: 0,
}

const sessionRowStyle: CSSProperties = {
  padding: '5px 7px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  display: 'grid',
  gap: 4,
}

const goalBtnStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
  flex: 1,
  minWidth: 0,
  textAlign: 'left',
}

const goalTextStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const stopBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--text-faint)',
  cursor: 'pointer',
  fontSize: 10,
  padding: '1px 3px',
  lineHeight: 1,
}

const outputBoxStyle: CSSProperties = {
  borderTop: '1px solid var(--border-dim)',
  paddingTop: 5,
  marginTop: 2,
}

const metaLineStyle: CSSProperties = {
  margin: '0 0 4px',
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
}

const outputTextStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  lineHeight: 1.5,
  whiteSpace: 'pre-wrap',
  maxHeight: 120,
  overflowY: 'auto',
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
  margin: 0,
}
