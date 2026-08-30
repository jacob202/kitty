'use client'

import { useState, type CSSProperties } from 'react'
import { useOperatorCommand } from '@/lib/queries'
import type { BuilderPacketStatus, BuilderInitiativeStatus } from '@/lib/gateway'

const controlsBar: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '6px 12px',
  borderBottom: '1px solid var(--line)',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
  flexWrap: 'wrap',
  minHeight: 34,
  boxSizing: 'border-box',
}

const globalControlsStyle: CSSProperties = {
  borderBottom: '1px solid var(--color-separator)',
  background: 'var(--color-surface)',
}

const globalControlsSummaryStyle: CSSProperties = {
  minHeight: 44,
  padding: '0 12px',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  cursor: 'pointer',
  color: 'var(--color-text-secondary)',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
}

const btnBase: CSSProperties = {
  background: 'none',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)',
  minHeight: 36,
  padding: '6px 10px',
  cursor: 'pointer',
  color: 'var(--color-text-primary)',
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  whiteSpace: 'nowrap',
}

const btnDisabled: CSSProperties = {
  ...btnBase,
  opacity: 0.4,
  cursor: 'not-allowed',
}

const btnDanger: CSSProperties = {
  ...btnBase,
  borderColor: '#F44336',
  color: '#F44336',
}

const btnWarning: CSSProperties = {
  ...btnBase,
  borderColor: '#FF9800',
  color: '#FF9800',
}

const btnConfirm: CSSProperties = {
  ...btnBase,
  background: '#F44336',
  color: '#fff',
  borderColor: '#F44336',
}

const confirmBar: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '6px 12px',
  borderBottom: '1px solid var(--line)',
  background: '#F4433611',
  fontSize: 11,
}

const errorBar: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 12px',
  borderBottom: '1px solid var(--line)',
  background: '#F4433611',
  fontSize: 10,
  color: '#F44336',
}

const successBar: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 12px',
  borderBottom: '1px solid var(--line)',
  background: '#4CAF5011',
  fontSize: 10,
  color: '#4CAF50',
}

type ConfirmAction = {
  action: string
  task_id?: string
  initiative_id?: string
  label: string
  target: string
} | null

interface ControlAction {
  key: string
  label: string
  action: string
  style?: CSSProperties
  disabled: boolean
  disabledReason: string
  confirmLabel?: string
  initiativeId?: string
  taskId?: string
}

interface OperatorControlsProps {
  snapshot: { initiatives: BuilderInitiativeStatus[] }
  selectedPacket: BuilderPacketStatus | null
}

function deriveActions(
  snapshot: OperatorControlsProps['snapshot'],
  selected: BuilderPacketStatus | null,
): ControlAction[] {
  const actions: ControlAction[] = []

  if (!selected) {
    const activeInitiatives = snapshot.initiatives.filter(i => i.state === 'active')
    for (const initiative of activeInitiatives) {
      actions.push({
        key: `pause-${initiative.initiative_id}`,
        label: `Pause ${initiative.title.slice(0, 20)}`,
        action: 'pause',
        initiativeId: initiative.initiative_id,
        disabled: false,
        disabledReason: '',
        style: btnWarning,
      })
    }
    const pausedInitiatives = snapshot.initiatives.filter(i => i.state === 'paused')
    for (const initiative of pausedInitiatives) {
      actions.push({
        key: `resume-${initiative.initiative_id}`,
        label: `Resume ${initiative.title.slice(0, 20)}`,
        action: 'resume',
        initiativeId: initiative.initiative_id,
        disabled: false,
        disabledReason: '',
      })
    }
    const hasAttention = snapshot.initiatives.some(i =>
      i.packets.some(p => p.task_state === 'blocked' || p.task_state === 'failed')
    )
    if (hasAttention) {
      actions.push({
        key: 'recover_stale',
        label: 'Recover stale',
        action: 'recover_stale',
        disabled: false,
        disabledReason: '',
        style: btnWarning,
      })
    }
    return actions
  }

  const taskId = selected.task_id
  const taskState = selected.task_state

  if (!taskId || !taskState) {
    return actions
  }

  const isRunning = taskState === 'running' || taskState === 'claimed'
  const isBlocked = taskState === 'blocked'

  if (isRunning) {
    actions.push({
      key: `cancel-${taskId}`,
      label: 'Cancel',
      action: 'cancel',
      taskId,
      disabled: false,
      disabledReason: '',
      style: btnDanger,
    })
    actions.push({
      key: `validate-${taskId}`,
      label: 'Run validation',
      action: 'run_validation',
      taskId,
      disabled: false,
      disabledReason: '',
    })
  }

  if (isBlocked) {
    actions.push({
      key: `requeue-${taskId}`,
      label: 'Requeue',
      action: 'requeue',
      taskId,
      disabled: false,
      disabledReason: '',
    })
    actions.push({
      key: `cancel-${taskId}`,
      label: 'Cancel',
      action: 'cancel',
      taskId,
      disabled: false,
      disabledReason: '',
      style: btnDanger,
    })
  }

  if (taskState === 'pr_opened' || taskState === 'awaiting_review') {
    actions.push({
      key: `publish-${taskId}`,
      label: 'Publish',
      action: 'publish',
      taskId,
      disabled: false,
      disabledReason: '',
      style: btnWarning,
    })
  }

  const initiative = snapshot.initiatives.find(
    i => i.initiative_id === selected.initiative_id
  )
  if (initiative) {
    if (initiative.state === 'active') {
      actions.push({
        key: `pause-${initiative.initiative_id}`,
        label: 'Pause initiative',
        action: 'pause',
        initiativeId: initiative.initiative_id,
        disabled: false,
        disabledReason: '',
        style: btnWarning,
      })
    } else if (initiative.state === 'paused') {
      actions.push({
        key: `resume-${initiative.initiative_id}`,
        label: 'Resume initiative',
        action: 'resume',
        initiativeId: initiative.initiative_id,
        disabled: false,
        disabledReason: '',
      })
    }
  }

  return actions
}

const destructiveActions = new Set(['cancel', 'publish', 'cleanup'])

function buildPayload(act: ControlAction): { action: string; task_id?: string; initiative_id?: string; packet_id?: string; reason: string } {
  return {
    action: act.action,
    task_id: act.taskId,
    initiative_id: act.initiativeId,
    reason: `operator ${act.action} from cockpit`,
  }
}

export function OperatorControls({ snapshot, selectedPacket }: OperatorControlsProps) {
  const command = useOperatorCommand()
  const [confirm, setConfirm] = useState<ConfirmAction>(null)
  const [lastResult, setLastResult] = useState<{ ok: boolean; text: string } | null>(null)

  const actions = deriveActions(snapshot, selectedPacket)

  const execute = (act: ControlAction) => {
    if (destructiveActions.has(act.action)) {
      const target = act.taskId ? `task ${act.taskId.slice(0, 8)}…` : (act.initiativeId || 'queue')
      setConfirm({ action: act.action, task_id: act.taskId, initiative_id: act.initiativeId, label: act.label, target })
      return
    }
    dispatch(act)
  }

  const dispatch = (act: ControlAction) => {
    setConfirm(null)
    setLastResult(null)
    command.mutate(buildPayload(act), {
      onSuccess: (data) => {
        if (data.ok) {
          setLastResult({ ok: true, text: data.detail || data.action || 'done' })
        } else {
          setLastResult({ ok: false, text: data.error || 'unknown error' })
        }
      },
      onError: (err) => {
        setLastResult({ ok: false, text: err instanceof Error ? err.message : 'request failed' })
      },
    })
  }

  const confirmAction = () => {
    if (!confirm) return
    const act = actions.find(a =>
      a.action === confirm.action &&
      a.taskId === confirm.task_id &&
      a.initiativeId === confirm.initiative_id
    )
    if (act) {
      dispatch(act)
    }
  }

  if (actions.length === 0 && !command.isPending && !lastResult) return null

  const controls = (
    <div style={controlsBar}>
      <span style={{ fontWeight: 700, fontSize: 10, letterSpacing: '0.05em', color: 'var(--color-text-muted)' }}>
        CONTROLS
      </span>
      {actions.map((act) => (
        <button
          key={act.key}
          type="button"
          disabled={act.disabled || command.isPending}
          onClick={() => execute(act)}
          style={act.disabled ? btnDisabled : (act.style || btnBase)}
          title={act.disabledReason || act.label}
        >
          {command.isPending && confirm?.action === act.action ? '…' : act.label}
        </button>
      ))}
      <div style={{ flex: 1 }} />
      <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
        {selectedPacket ? selectedPacket.packet_id.slice(0, 8) + '…' : 'no selection'}
      </span>
    </div>
  )

  return (
    <>
      {confirm && (
        <div style={confirmBar}>
          <span style={{ color: 'var(--ink)', flex: 1 }}>
            {confirm.label} — {confirm.target}?
          </span>
          <button
            type="button"
            disabled={command.isPending}
            onClick={confirmAction}
            style={btnConfirm}
          >
            {command.isPending ? '…' : 'confirm'}
          </button>
          <button
            type="button"
            onClick={() => setConfirm(null)}
            style={btnBase}
          >
            cancel
          </button>
        </div>
      )}

      {lastResult && !confirm && (
        <div style={lastResult.ok ? successBar : errorBar}>
          <span>{lastResult.text}</span>
          <button
            type="button"
            onClick={() => setLastResult(null)}
            style={{ ...btnBase, fontSize: 9, marginLeft: 'auto' }}
          >
            dismiss
          </button>
        </div>
      )}

      {selectedPacket ? controls : (
        <details style={globalControlsStyle}>
          <summary style={globalControlsSummaryStyle}>
            Global controls
            <span style={{ color: 'var(--color-text-muted)', fontWeight: 500 }}>{actions.length}</span>
          </summary>
          {controls}
        </details>
      )}
    </>
  )
}
