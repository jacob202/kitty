'use client'
import { useState, useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { createGatewayTask, fetchGatewayTasks, cancelGatewayTask, type GatewayTask, type TaskType } from '@/lib/gateway'

const TASK_TYPES: { id: TaskType; label: string }[] = [
  { id: 'research',  label: 'research' },
  { id: 'build',     label: 'build'    },
  { id: 'cleanup',   label: 'cleanup'  },
  { id: 'dream',     label: 'dream'    },
]

const STATUS_COLOR: Record<string, string> = {
  queued:    'var(--text-muted)',
  running:   'var(--orange)',
  completed: 'var(--teal)',
  failed:    '#ff5577',
  cancelled: 'var(--text-faint)',
}

export function TaskPanel() {
  const [tasks, setTasks]           = useState<GatewayTask[]>([])
  const [goal, setGoal]             = useState('')
  const [taskType, setTaskType]     = useState<TaskType>('research')
  const [launching, setLaunching]   = useState(false)
  const inputRef                    = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let alive = true
    const poll = async () => {
      const next = await fetchGatewayTasks(6)
      if (alive) setTasks(next)
    }
    void poll()
    const id = setInterval(() => { void poll() }, 3000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const hasActive = tasks.some(t => t.status === 'queued' || t.status === 'running')

  async function handleLaunch() {
    const g = goal.trim()
    if (!g || launching) return
    setLaunching(true)
    const id = await createGatewayTask(g, taskType)
    setLaunching(false)
    if (id) {
      setGoal('')
      const next = await fetchGatewayTasks(6)
      setTasks(next)
    }
  }

  async function handleCancel(id: string) {
    await cancelGatewayTask(id)
    const next = await fetchGatewayTasks(6)
    setTasks(next)
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {/* Launch form */}
      <div style={formStyle}>
        <div style={typeRowStyle}>
          {TASK_TYPES.map(t => (
            <button
              key={t.id}
              onClick={() => setTaskType(t.id)}
              style={{
                ...typeButtonStyle,
                background: taskType === t.id ? 'rgba(232,120,69,0.18)' : 'transparent',
                color: taskType === t.id ? 'var(--orange-2)' : 'var(--text-muted)',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div style={inputRowStyle}>
          <input
            ref={inputRef}
            value={goal}
            onChange={e => setGoal(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && void handleLaunch()}
            placeholder="describe the task goal…"
            style={inputStyle}
          />
          <button
            onClick={() => void handleLaunch()}
            disabled={!goal.trim() || launching}
            style={{
              ...launchButtonStyle,
              opacity: !goal.trim() || launching ? 0.4 : 1,
            }}
          >
            {launching ? '…' : 'run'}
          </button>
        </div>
      </div>

      {/* Task list */}
      {tasks.length > 0 && (
        <div style={{ display: 'grid', gap: 5 }}>
          {tasks.map(task => (
            <div key={task.task_id} style={taskRowStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <span style={taskTypeTagStyle}>{task.task_type}</span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: '0.04em',
                  color: STATUS_COLOR[task.status],
                  textTransform: 'uppercase',
                }}>
                  {task.status}
                </span>
                {(task.status === 'queued' || task.status === 'running') && (
                  <button onClick={() => void handleCancel(task.task_id)} style={cancelButtonStyle}>
                    cancel
                  </button>
                )}
              </div>
              <p style={taskGoalStyle}>{task.goal.slice(0, 100)}{task.goal.length > 100 ? '…' : ''}</p>
              {task.status === 'failed' && task.error && (
                <p style={{ ...progressStyle, color: STATUS_COLOR.failed }}>{task.error.slice(0, 80)}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {tasks.length === 0 && (
        <p style={emptyStyle}>no tasks yet — launch one above</p>
      )}

      {hasActive && (
        <p style={{ ...emptyStyle, color: 'var(--orange)' }}>● active</p>
      )}
    </div>
  )
}

const formStyle: CSSProperties = {
  display: 'grid',
  gap: 6,
}

const typeRowStyle: CSSProperties = {
  display: 'flex',
  gap: 3,
  padding: 3,
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 6,
}

const typeButtonStyle: CSSProperties = {
  flex: 1,
  padding: '4px 6px',
  borderRadius: 4,
  border: 'none',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  cursor: 'pointer',
  transition: 'background 0.1s',
}

const inputRowStyle: CSSProperties = {
  display: 'flex',
  gap: 6,
}

const inputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  padding: '6px 9px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
  minWidth: 0,
}

const launchButtonStyle: CSSProperties = {
  flexShrink: 0,
  padding: '6px 12px',
  background: 'rgba(232,120,69,0.15)',
  border: '1px solid rgba(232,120,69,0.3)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--orange-2)',
  cursor: 'pointer',
}

const taskRowStyle: CSSProperties = {
  padding: '7px 9px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  display: 'grid',
  gap: 3,
}

const statusDotStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  display: 'flex',
  alignItems: 'center',
  gap: 4,
}

const taskTypeTagStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
}

const taskGoalStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  lineHeight: 1.4,
}

const progressStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  lineHeight: 1.4,
}

const cancelButtonStyle: CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--border-dim)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  padding: '2px 6px',
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
}
