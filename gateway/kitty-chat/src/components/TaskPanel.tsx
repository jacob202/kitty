'use client'
import { useState, useRef } from 'react'
import type { CSSProperties } from 'react'
import { type GatewayTask, type TaskType } from '@/lib/gateway'
import { useTasks, useCreateTask, useCancelTask } from '@/lib/queries'

const TYPE_META: Record<TaskType, { label: string; description: string; color: string; example: string }> = {
  research: { label: 'Research', description: 'Deep dive on a topic',     color: 'var(--purple)', example: 'e.g. summarize recent LLM evals…' },
  ingest:   { label: 'Ingest',   description: 'Process & store knowledge', color: 'var(--indigo)', example: 'e.g. index my reading list…' },
  build:    { label: 'Build',    description: 'Write or modify code',      color: 'var(--orange)', example: 'e.g. add auth to the API…' },
  cleanup:  { label: 'Cleanup',  description: 'Refactor, prune, tidy up', color: 'var(--teal)',   example: 'e.g. remove dead utility files…' },
  dream:    { label: 'Dream',    description: 'Speculate freely',          color: 'var(--mint)',   example: 'e.g. how could kitty learn music…' },
}

const STATUS_COLOR: Record<string, string> = {
  queued:    'var(--text-muted)',
  running:   'var(--orange)',
  completed: 'var(--teal)',
  failed:    '#ff5577',
  cancelled: 'var(--text-faint)',
}

const STATUS_ICON: Record<string, string> = {
  queued:    '○',
  running:   '●',
  completed: '✓',
  failed:    '✗',
  cancelled: '–',
}

export function TaskPanel() {
  const tasksQuery = useTasks(12)
  const createTask = useCreateTask()
  const cancelTask = useCancelTask()

  const tasks = tasksQuery.data ?? []
  const launching = createTask.isPending

  const [goal, setGoal] = useState('')
  const [taskType, setTaskType] = useState<TaskType>('research')
  const inputRef = useRef<HTMLInputElement>(null)

  const activeTasks = tasks.filter(t => t.status === 'queued' || t.status === 'running')
  const recentTasks = tasks.filter(t => t.status !== 'queued' && t.status !== 'running')
  const meta = TYPE_META[taskType]

  function handleLaunch() {
    const g = goal.trim()
    if (!g || launching) return
    createTask.mutate(
      { goal: g, taskType },
      { onSuccess: id => { if (id) setGoal('') } },
    )
  }

  function handleCancel(id: string) {
    cancelTask.mutate(id)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', minHeight: 0 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20, flexShrink: 0 }}>
        <div>
          <div style={sectionLabelStyle}>task runner</div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 22, fontWeight: 700, color: 'var(--text)', lineHeight: 1.1, marginTop: 4 }}>
            What should Kitty work on?
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
          <StatChip label="active" value={String(activeTasks.length)} color="var(--orange)" />
          <StatChip label="done" value={String(recentTasks.filter(t => t.status === 'completed').length)} color="var(--teal)" />
          <StatChip label="failed" value={String(recentTasks.filter(t => t.status === 'failed').length)} color="#ff5577" />
        </div>
      </div>

      {/* Type selector */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8, marginBottom: 16, flexShrink: 0 }}>
        {(Object.keys(TYPE_META) as TaskType[]).map(type => {
          const m = TYPE_META[type]
          const active = taskType === type
          return (
            <button
              key={type}
              onClick={() => setTaskType(type)}
              style={{
                flex: 1,
                padding: '10px 10px 10px',
                borderRadius: 10,
                border: `1px solid ${active ? m.color : 'var(--border)'}`,
                background: active ? `${m.color}1a` : 'var(--surface-low)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.borderColor = m.color
                  el.style.background = `${m.color}0d`
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.borderColor = 'var(--border)'
                  el.style.background = 'var(--surface-low)'
                }
              }}
            >
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                fontWeight: 700,
                color: active ? m.color : 'var(--text-dim)',
                letterSpacing: '0.04em',
                marginBottom: 4,
              }}>{m.label}</div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: active ? `${m.color}bb` : 'var(--text-ghost)',
                lineHeight: 1.4,
              }}>{m.description}</div>
            </button>
          )
        })}
      </div>

      {/* Launch form */}
      <div style={{
        background: 'var(--surface-low)',
        border: `1px solid ${meta.color}50`,
        borderRadius: 12,
        padding: '16px',
        marginBottom: 20,
        flexShrink: 0,
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 10,
        }}>
          <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: meta.color, flexShrink: 0 }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: meta.color, letterSpacing: '0.14em', textTransform: 'uppercase' as const, fontWeight: 700 }}>
            {meta.label} task
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <input
            ref={inputRef}
            value={goal}
            onChange={e => setGoal(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLaunch()}
            placeholder={meta.example}
            style={{
              flex: 1,
              background: 'var(--surface-mid)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '10px 14px',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--text)',
              outline: 'none',
              minWidth: 0,
            }}
          />
          <button
            onClick={handleLaunch}
            disabled={!goal.trim() || launching}
            style={{
              flexShrink: 0,
              padding: '10px 20px',
              background: !goal.trim() || launching ? 'var(--surface-mid)' : `${meta.color}22`,
              border: `1px solid ${!goal.trim() || launching ? 'var(--border)' : meta.color}`,
              borderRadius: 8,
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              fontWeight: 700,
              color: !goal.trim() || launching ? 'var(--text-muted)' : meta.color,
              cursor: !goal.trim() || launching ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
              letterSpacing: '0.04em',
              whiteSpace: 'nowrap' as const,
            }}
          >
            {launching ? '…' : 'launch →'}
          </button>
        </div>
      </div>

      {/* Task list */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {activeTasks.length > 0 && (
          <section>
            <div style={sectionLabelStyle}>Active</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {activeTasks.map(task => (
                <TaskCard key={task.task_id} task={task} onCancel={handleCancel} />
              ))}
            </div>
          </section>
        )}

        {recentTasks.length > 0 && (
          <section>
            <div style={sectionLabelStyle}>Recent</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
              {recentTasks.map(task => (
                <TaskCard key={task.task_id} task={task} onCancel={handleCancel} />
              ))}
            </div>
          </section>
        )}

        {tasks.length === 0 && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: '48px 0' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 40, color: 'var(--surface-high)', lineHeight: 1 }}>◎</div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-faint)', marginBottom: 4 }}>no tasks yet</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-ghost)' }}>pick a type above and describe a goal</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      background: 'var(--surface-low)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '8px 14px',
      textAlign: 'center',
      minWidth: 48,
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-ghost)', letterSpacing: '0.1em', textTransform: 'uppercase' as const, marginTop: 3 }}>{label}</div>
    </div>
  )
}

function TaskCard({ task, onCancel }: { task: GatewayTask; onCancel: (id: string) => void }) {
  const statusColor = STATUS_COLOR[task.status] ?? 'var(--text-muted)'
  const icon = STATUS_ICON[task.status] ?? '○'
  const typeColor = TYPE_META[task.task_type as TaskType]?.color ?? 'var(--indigo)'
  const isActive = task.status === 'queued' || task.status === 'running'

  return (
    <div style={{
      background: 'var(--surface-low)',
      border: '1px solid var(--border)',
      borderLeft: `3px solid ${statusColor}`,
      borderRadius: '0 10px 10px 0',
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, minWidth: 0, flex: 1 }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            color: statusColor,
            flexShrink: 0,
            lineHeight: 1.2,
            marginTop: 1,
          }}>{icon}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--text)',
              lineHeight: 1.5,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap' as const,
            }}>{task.goal}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 5 }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: typeColor,
                fontWeight: 700,
                letterSpacing: '0.1em',
                textTransform: 'uppercase' as const,
              }}>{task.task_type}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-ghost)', letterSpacing: '0.06em' }}>{task.status}</span>
              {task.created_at && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-ghost)' }}>
                  {new Date(task.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          </div>
        </div>
        {isActive && (
          <button
            onClick={() => onCancel(task.task_id)}
            style={{
              flexShrink: 0,
              background: 'transparent',
              border: '1px solid var(--border-dim)',
              borderRadius: 5,
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '3px 8px',
              letterSpacing: '0.06em',
            }}
          >cancel</button>
        )}
      </div>
      {task.status === 'failed' && task.error && (
        <div style={{
          marginTop: 8,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: STATUS_COLOR.failed,
          lineHeight: 1.4,
          padding: '6px 8px',
          background: 'rgba(255,85,119,0.06)',
          borderRadius: 5,
        }}>
          {task.error.slice(0, 120)}
        </div>
      )}
    </div>
  )
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  color: 'var(--text-ghost)',
  letterSpacing: '0.18em',
  textTransform: 'uppercase',
}
