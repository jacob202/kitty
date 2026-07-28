'use client'
import { useState, useRef, type CSSProperties } from 'react'
import { type TaskType } from '@/lib/gateway'
import { useTasks, useCreateTask, useCancelTask, useTaskOutput } from '@/lib/queries'
import { WorkCard, type WorkStatus } from '@/components/shared/WorkCard'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/StatusBadge'

const TYPE_META: Record<TaskType, { label: string; description: string; color: string }> = {
  research: { label: 'research', description: 'deep dive',     color: 'var(--c-purple)' },
  ingest:   { label: 'ingest',   description: 'store knowledge', color: 'var(--c-purple)' },
  build:    { label: 'build',    description: 'code',           color: 'var(--cat-ginger)' },
  cleanup:  { label: 'cleanup',  description: 'refactor',      color: 'var(--c-blue)' },
  dream:    { label: 'dream',    description: 'speculate',     color: 'var(--c-green)' },
}

const STATUS_MAP: Record<string, WorkStatus> = {
  queued: 'scheduled', running: 'working', completed: 'completed', failed: 'failed', cancelled: 'canceled',
}

export function TaskPanel() {
  const tasksQuery = useTasks(12)
  const createTask = useCreateTask()
  const cancelTask = useCancelTask()
  const tasks = tasksQuery.data ?? []
  const [goal, setGoal] = useState('')
  const [taskType, setTaskType] = useState<TaskType>('research')
  const inputRef = useRef<HTMLInputElement>(null)

  const activeTasks = tasks.filter(t => t.status === 'queued' || t.status === 'running')
  const recentTasks = tasks.filter(t => t.status !== 'queued' && t.status !== 'running')

  function handleLaunch() {
    const g = goal.trim()
    if (!g || createTask.isPending) return
    createTask.mutate({ goal: g, taskType }, { onSuccess: () => setGoal('') })
  }

  const launchError = createTask.isError
    ? (createTask.error instanceof Error ? createTask.error.message : 'gateway rejected the task')
    : null
  const cancelError = cancelTask.isError
    ? (cancelTask.error instanceof Error ? cancelTask.error.message : 'gateway rejected the cancel')
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <StatusBadge state="working" label={`${activeTasks.length} active`} />
        <StatusBadge state="completed" label={`${recentTasks.filter(t => t.status === 'completed').length} done`} />
        <StatusBadge state="failed" label={`${recentTasks.filter(t => t.status === 'failed').length} failed`} />
      </div>

      {/* New task input */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {(Object.keys(TYPE_META) as TaskType[]).map(type => (
            <button
              key={type}
              onClick={() => setTaskType(type)}
              style={{
                padding: '4px 10px', borderRadius: 99, fontSize: 11, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                border: `1.5px solid ${type === taskType ? TYPE_META[type].color : 'var(--line)'}`,
                background: type === taskType ? `${TYPE_META[type].color}15` : 'transparent',
                color: type === taskType ? TYPE_META[type].color : 'var(--ink-2)',
              }}
            >
              {TYPE_META[type].label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          ref={inputRef}
          value={goal}
          onChange={e => setGoal(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleLaunch() }}
          placeholder={`${TYPE_META[taskType].label}: what should kitty do?`}
          style={{
            flex: 1, padding: '8px 14px', borderRadius: 10, border: '1.5px solid var(--line)',
            background: 'var(--surface)', fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--ink)',
            outline: 'none',
          }}
        />
        <Button onClick={handleLaunch} size="sm" disabled={!goal.trim() || createTask.isPending}>
          {createTask.isPending ? 'adding…' : 'add'}
        </Button>
      </div>

      {launchError && <p style={errorStyle}>couldn&apos;t start that task — {launchError}</p>}
      {cancelError && <p style={errorStyle}>couldn&apos;t cancel — {cancelError}</p>}
      {tasksQuery.isError && (
        <p style={errorStyle}>
          can&apos;t read the task list — {tasksQuery.error instanceof Error ? tasksQuery.error.message : 'gateway error'}
        </p>
      )}

      {/* Active tasks */}
      {activeTasks.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {activeTasks.map(task => (
            <WorkCard
              key={task.task_id}
              id={task.task_id}
              title={task.goal ?? task.task_id}
              status={STATUS_MAP[task.status] ?? 'scheduled'}
              statusDetail={task.progress ? `${task.task_type} — ${task.progress}` : task.task_type}
              onCancel={() => cancelTask.mutate(task.task_id)}
            />
          ))}
        </div>
      )}

      {/* Completed / recent */}
      {recentTasks.length > 0 && (
        <details style={{ marginTop: 8 }} open>
          <summary style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)', cursor: 'pointer', marginBottom: 12 }}>
            recent ({recentTasks.length})
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recentTasks.map(task => (
              <FinishedTask
                key={task.task_id}
                taskId={task.task_id}
                title={task.goal ?? task.task_id}
                status={STATUS_MAP[task.status] ?? 'completed'}
                taskType={task.task_type}
                error={task.error ?? null}
              />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

/** A finished task is useless if you can't read what it produced. The output is
 *  fetched on expand rather than with the list — these files can be long. */
function FinishedTask({
  taskId, title, status, taskType, error,
}: {
  taskId: string
  title: string
  status: WorkStatus
  taskType: string
  error: string | null
}) {
  const [open, setOpen] = useState(false)
  const outputQuery = useTaskOutput(open ? taskId : null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <WorkCard
        id={taskId}
        title={title}
        status={status}
        statusDetail={error ? `${taskType} — ${error}` : taskType}
      />
      <button type="button" onClick={() => setOpen(o => !o)} style={disclosureStyle}>
        {open ? 'hide output' : 'show output'}
      </button>
      {open && (
        <div style={outputBoxStyle}>
          {outputQuery.isLoading && <span style={{ color: 'var(--ink-2)' }}>loading output…</span>}
          {outputQuery.isError && (
            <span style={{ color: 'var(--c-red)' }}>
              couldn&apos;t read the output — {outputQuery.error instanceof Error ? outputQuery.error.message : 'gateway error'}
            </span>
          )}
          {outputQuery.isSuccess && (
            outputQuery.data
              ? <pre style={preStyle}>{outputQuery.data}</pre>
              : <span style={{ color: 'var(--ink-2)' }}>this task wrote no output.</span>
          )}
        </div>
      )}
    </div>
  )
}

const errorStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--c-red)',
  lineHeight: 1.5,
}

const disclosureStyle: CSSProperties = {
  alignSelf: 'flex-start',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  background: 'transparent',
  border: '1px solid var(--line)',
  borderRadius: 6,
  padding: '2px 8px',
  cursor: 'pointer',
}

const outputBoxStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 8,
  padding: 10,
  maxHeight: 320,
  overflow: 'auto',
}

const preStyle: CSSProperties = {
  margin: 0,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  color: 'var(--ink)',
}
