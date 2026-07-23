'use client'
import { useState, useRef } from 'react'
import { type GatewayTask, type TaskType } from '@/lib/gateway'
import { useTasks, useCreateTask, useCancelTask } from '@/lib/queries'
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
        <Button onClick={handleLaunch} size="sm" disabled={!goal.trim() || createTask.isPending}>add</Button>
      </div>

      {/* Active tasks */}
      {activeTasks.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {activeTasks.map(task => (
            <WorkCard
              key={task.task_id}
              id={task.task_id}
              title={task.goal ?? task.task_id}
              status={STATUS_MAP[task.status] ?? 'scheduled'}
              statusDetail={task.task_type}
              onCancel={() => cancelTask.mutate(task.task_id)}
            />
          ))}
        </div>
      )}

      {/* Completed / recent */}
      {recentTasks.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)', cursor: 'pointer', marginBottom: 12 }}>
            recent ({recentTasks.length})
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recentTasks.map(task => (
              <WorkCard
                key={task.task_id}
                id={task.task_id}
                title={task.goal ?? task.task_id}
                status={STATUS_MAP[task.status] ?? 'completed'}
                statusDetail={task.task_type}
              />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
