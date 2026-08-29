'use client'
import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { type CronScheduleType, type WhyStatus } from '@/lib/gateway'
import {
  useCronSchedules, useCronActions, useCreateCronSchedule,
  useUpdateCronSchedule, useDeleteCronSchedule, useToggleCronSchedule,
  useScheduleWhy,
} from '@/lib/queries'

function fmtLastRun(ts: number): string {
  if (!ts) return 'never'
  const diff = Math.floor((Date.now() / 1000) - ts)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function valueHint(t: CronScheduleType): string {
  if (t === 'daily') return 'HH:MM (e.g. 07:00)'
  if (t === 'interval') return 'minutes (e.g. 30)'
  return 'ISO datetime (e.g. 2026-06-01T09:00)'
}

function valuePlaceholder(t: CronScheduleType): string {
  if (t === 'daily') return '07:00'
  if (t === 'interval') return '30'
  return '2026-06-01T09:00'
}

export function CronPanel({ variant = 'compact', isMobile = false }: { variant?: 'compact' | 'full'; isMobile?: boolean }) {
  const schedulesQuery = useCronSchedules()
  const actionsQuery = useCronActions()
  const createSchedule = useCreateCronSchedule()
  const updateSchedule = useUpdateCronSchedule()
  const deleteSchedule = useDeleteCronSchedule()
  const toggleSchedule = useToggleCronSchedule()

  const schedules = schedulesQuery.data ?? []
  const actions = actionsQuery.data ?? []
  const activeCount = schedules.filter(s => s.enabled).length
  const saving = createSchedule.isPending || updateSchedule.isPending

  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [whyId, setWhyId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [action, setAction] = useState('')
  const [schedType, setSchedType] = useState<CronScheduleType>('daily')
  const [schedVal, setSchedVal] = useState('07:00')

  const whyQuery = useScheduleWhy(whyId)

  function toggleWhy(id: string) {
    setWhyId(whyId === id ? null : id)
  }

  // Default the action picker to the first known action once they load.
  useEffect(() => {
    if (!action && actions.length > 0) setAction(actions[0])
  }, [actions, action])

  function resetForm() {
    setName('')
    setSchedVal(valuePlaceholder(schedType))
    setAdding(false)
    setEditingId(null)
  }

  function handleSave() {
    if (!name.trim() || !action || !schedVal.trim() || saving) return
    if (editingId) {
      updateSchedule.mutate(
        { id: editingId, name: name.trim(), action, scheduleType: schedType, scheduleValue: schedVal.trim() },
        { onSuccess: resetForm },
      )
      return
    }
    createSchedule.mutate(
      { name: name.trim(), action, scheduleType: schedType, scheduleValue: schedVal.trim() },
      {
        onSuccess: id => {
          if (id) resetForm()
        },
      },
    )
  }

  function startEdit(schedule: typeof schedules[number]) {
    setAdding(false)
    setEditingId(schedule.id)
    setName(schedule.name)
    setAction(schedule.action)
    setSchedType(schedule.schedule_type)
    setSchedVal(schedule.schedule_value)
  }

  function handleTypeChange(t: CronScheduleType) {
    setSchedType(t)
    setSchedVal(valuePlaceholder(t))
  }

  const formOpen = adding || editingId !== null
  const full = variant === 'full'

  if (schedulesQuery.isPending) {
    return <div style={asyncNoticeStyle}>Loading schedules…</div>
  }

  if (schedulesQuery.isError) {
    return (
      <div style={asyncNoticeStyle}>
        <span>Schedules are unavailable right now.</span>
        <button type="button" onClick={() => void schedulesQuery.refetch()} style={asyncRetryStyle}>Retry schedules</button>
      </div>
    )
  }

  return (
    <div data-testid={full ? 'automations-list' : undefined} style={{ display: 'grid', gap: full ? 14 : 8 }}>
      <p style={full ? fullSummaryStyle : summaryStyle}>{activeCount}/{schedules.length} active</p>

      {/* Schedule list */}
      {schedules.length > 0 ? (
        <div data-testid={full ? 'automation-schedule-list' : undefined} style={full ? fullListStyle : { display: 'grid', gap: 4 }}>
          {schedules.map((s, index) => (
            <div key={s.id} data-testid={full ? 'automation-schedule-row' : undefined} style={full ? fullRowStyle(s.enabled, index === schedules.length - 1) : rowStyle(s.enabled)}>
              {full ? (
                <>
                  <div style={isMobile ? fullRowHeaderMobileStyle : fullRowHeaderStyle}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={fullNameLineStyle}>
                        <strong style={fullNameStyle}>{s.name}</strong>
                        <span style={statusPillStyle(Boolean(s.enabled))}>{s.enabled ? 'Active' : 'Paused'}</span>
                      </div>
                      <p style={scheduleSentenceStyle}>{scheduleSentence(s)}</p>
                      <p style={actionSentenceStyle}>Kitty runs {humanAction(s.action)}</p>
                      <p style={lastRunStyle}>Last run: {fmtLastRun(s.last_run)}</p>
                    </div>
                    <div data-testid="automation-schedule-actions" style={isMobile ? fullActionsMobileStyle : fullActionsStyle}>
                      <button
                        type="button"
                        onClick={() => toggleWhy(s.id)}
                        style={fullActionButtonStyle}
                        aria-label={`Why did ${s.name} not run?`}
                      >Why?</button>
                      <button
                        type="button"
                        onClick={() => toggleSchedule.mutate(s.id)}
                        style={fullActionButtonStyle}
                        aria-label={`${s.enabled ? 'Pause' : 'Resume'} ${s.name}`}
                      >{s.enabled ? 'Pause' : 'Resume'}</button>
                      <button
                        type="button"
                        onClick={() => startEdit(s)}
                        style={fullActionButtonStyle}
                        aria-label={`Edit ${s.name}`}
                      >Edit</button>
                      <button
                        type="button"
                        onClick={() => deleteSchedule.mutate(s.id)}
                        style={{ ...fullActionButtonStyle, color: 'var(--color-destructive)' }}
                        aria-label={`Delete ${s.name}`}
                      >Delete</button>
                    </div>
                  </div>
                  {whyId === s.id && (
                    <div style={fullWhyBoxStyle}>
                      {whyQuery.isPending ? (
                        <p style={fullMetaStyle}>Checking the run record…</p>
                      ) : whyQuery.isError ? (
                        <p style={fullMetaStyle}>Couldn&apos;t explain this run right now.</p>
                      ) : whyQuery.data ? (
                        <>
                          <p style={whyStatusStyle(whyQuery.data.status)}>{whyQuery.data.status.replace(/_/g, ' ')}</p>
                          <p style={fullMetaStyle}>{whyQuery.data.reason}</p>
                          {whyQuery.data.relevant_at ? <p style={fullMetaStyle}>Relevant time: {fmtTimestamp(whyQuery.data.relevant_at)}</p> : null}
                          {whyQuery.data.next_step ? <p style={fullMetaStyle}>Next: {whyQuery.data.next_step}</p> : null}
                        </>
                      ) : null}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <p style={nameStyle}>{s.name}</p>
                      <p style={metaStyle}>
                        <span style={typeBadgeStyle(s.schedule_type)}>{s.schedule_type}</span>
                        {' '}{s.schedule_value}
                        {' · '}{s.action}
                        {' · last '}{fmtLastRun(s.last_run)}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: 3, flexShrink: 0, alignItems: 'center' }}>
                      <button onClick={() => toggleWhy(s.id)} style={whyBtnStyle} title="why didn't this happen?" aria-label="why schedule">?</button>
                      <button onClick={() => toggleSchedule.mutate(s.id)} style={{ ...toggleBtnStyle, color: s.enabled ? 'var(--color-accent)' : 'var(--color-text-secondary)' }} title={s.enabled ? 'disable' : 'enable'} aria-label={s.enabled ? 'disable schedule' : 'enable schedule'}>{s.enabled ? '●' : '○'}</button>
                      <button onClick={() => startEdit(s)} style={editBtnStyle} title="edit" aria-label="edit schedule">✎</button>
                      <button onClick={() => deleteSchedule.mutate(s.id)} style={deleteBtnStyle} title="delete" aria-label="delete schedule">×</button>
                    </div>
                  </div>
                  {whyId === s.id && (
                    <div style={whyBoxStyle}>
                      {whyQuery.isPending ? (
                        <p style={metaStyle}>checking…</p>
                      ) : whyQuery.isError ? (
                        <p style={metaStyle}>couldn&apos;t explain: {String((whyQuery.error as Error).message ?? whyQuery.error)}</p>
                      ) : whyQuery.data ? (
                        <>
                          <p style={whyStatusStyle(whyQuery.data.status)}>{whyQuery.data.status.replace(/_/g, ' ')}</p>
                          <p style={metaStyle}>{whyQuery.data.reason}</p>
                          {whyQuery.data.relevant_at ? <p style={metaStyle}>at {fmtTimestamp(whyQuery.data.relevant_at)}</p> : null}
                          {whyQuery.data.next_step ? <p style={metaStyle}>next: {whyQuery.data.next_step}</p> : null}
                        </>
                      ) : null}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p style={full ? fullEmptyStyle : emptyStyle}>{full ? 'No automations yet.' : 'no schedules yet'}</p>
      )}

      {/* Add form */}
      {formOpen ? (
        <div style={full ? fullFormStyle : formStyle}>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="name"
            style={full ? fullInputStyle : inputStyle}
          />
          {actions.length > 0 ? (
            <select value={action} onChange={e => setAction(e.target.value)} style={full ? fullInputStyle : inputStyle}>
              {actions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          ) : (
            <input
              value={action}
              onChange={e => setAction(e.target.value)}
              placeholder="action name"
              style={full ? fullInputStyle : inputStyle}
            />
          )}
          <div style={{ display: 'flex', gap: 4 }}>
            {(['daily', 'interval', 'once'] as CronScheduleType[]).map(t => (
              <button
                key={t}
                onClick={() => handleTypeChange(t)}
                style={{
                  ...(full ? fullTypeChipStyle : typeChipStyle),
                  background: schedType === t ? 'rgba(102,119,204,0.16)' : 'transparent',
                  color: schedType === t ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                  borderColor: schedType === t ? 'rgba(102,119,204,0.35)' : 'var(--color-separator)',
                }}
              >
                {t}
              </button>
            ))}
          </div>
          <input
            value={schedVal}
            onChange={e => setSchedVal(e.target.value)}
            placeholder={valuePlaceholder(schedType)}
            title={valueHint(schedType)}
            style={full ? fullInputStyle : inputStyle}
          />
          <div style={{ display: 'flex', gap: 5 }}>
            <button
              onClick={handleSave}
              disabled={!name.trim() || !action || !schedVal.trim() || saving}
              style={{ ...saveBtnStyle, flex: 1, opacity: !name.trim() || saving ? 0.4 : 1 }}
            >
              {saving ? 'saving…' : editingId ? 'update' : 'save'}
            </button>
            <button onClick={resetForm} style={cancelBtnStyle}>cancel</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} style={full ? fullAddButtonStyle : addBtnStyle}>{full ? 'Add automation' : '+ add schedule'}</button>
      )}
    </div>
  )
}

function scheduleSentence(schedule: { schedule_type: CronScheduleType; schedule_value: string }): string {
  if (schedule.schedule_type === 'daily') return `Every day at ${schedule.schedule_value}`
  if (schedule.schedule_type === 'interval') {
    const amount = Number(schedule.schedule_value)
    return `Every ${schedule.schedule_value} ${amount === 1 ? 'minute' : 'minutes'}`
  }
  return `Once at ${schedule.schedule_value}`
}

function humanAction(action: string): string {
  return action.replace(/[._-]+/g, ' ').replace(/\s+/g, ' ').trim()
}

function fmtTimestamp(ts: number): string {
  return new Date(ts * 1000).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
}

function whyStatusStyle(status: WhyStatus): CSSProperties {
  const color =
    status === 'completed' || status === 'not_yet_due' || status === 'already_claimed' || status === 'claimed' || status === 'pending_claim' || status === 'not_triggered'
      ? 'var(--color-success)'
      : status === 'failed' || status === 'execution_gap' || status === 'action_unavailable' || status === 'policy_refused' || status === 'grant_revoked' || status === 'source_unavailable'
        ? 'var(--color-destructive)'
        : 'var(--color-warning)'
  return {
    margin: 0,
    fontFamily: 'var(--font-mono)',
    fontSize: 10,
    fontWeight: 600,
    color,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  }
}

function rowStyle(enabled: number): CSSProperties {
  return {
    padding: '5px 7px',
    background: enabled ? 'var(--color-surface-elevated)' : 'transparent',
    border: `1px solid ${enabled ? 'var(--color-separator)' : 'var(--color-separator)'}`,
    borderRadius: 4,
    opacity: enabled ? 1 : 0.5,
  }
}

function typeBadgeStyle(type: string): CSSProperties {
  const color = type === 'daily' ? 'var(--color-accent)'
    : type === 'interval' ? 'var(--color-accent)'
    : 'var(--cat-ginger)'
  return { fontFamily: 'var(--font-mono)', fontSize: 9, color, textTransform: 'lowercase', letterSpacing: '0.06em' }
}

const nameStyle: CSSProperties = {
  margin: '0 0 2px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--color-text-secondary)',
}

const metaStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--color-text-secondary)',
}

const toggleBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontSize: 11,
  padding: '1px 3px',
  lineHeight: 1,
}

const whyBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--color-accent)',
  cursor: 'pointer',
  fontSize: 11,
  padding: '1px 3px',
  lineHeight: 1,
  fontFamily: 'var(--font-mono)',
}

const whyBoxStyle: CSSProperties = {
  display: 'grid',
  gap: 3,
  marginTop: 5,
  padding: '5px 7px',
  background: 'rgba(102,119,204,0.08)',
  border: '1px solid var(--color-separator)',
  borderRadius: 4,
}

const deleteBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--color-text-secondary)',
  cursor: 'pointer',
  fontSize: 13,
  padding: '1px 3px',
  lineHeight: 1,
}

const editBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--color-text-secondary)',
  cursor: 'pointer',
  fontSize: 12,
  padding: '1px 3px',
  lineHeight: 1,
}

const summaryStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--color-text-secondary)',
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--color-text-secondary)',
}

const formStyle: CSSProperties = {
  display: 'grid',
  gap: 5,
  padding: '8px 10px',
  background: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-separator)',
  borderRadius: 4,
}

const inputStyle: CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 4,
  padding: '4px 7px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--color-text-secondary)',
  outline: 'none',
}

const typeChipStyle: CSSProperties = {
  padding: '2px 7px',
  border: '1px solid var(--color-separator)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  cursor: 'pointer',
}

const saveBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'rgba(102,119,204,0.12)',
  border: '1px solid rgba(102,119,204,0.3)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--color-accent)',
  cursor: 'pointer',
}

const cancelBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'transparent',
  border: '1px solid var(--color-separator)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--color-text-secondary)',
  cursor: 'pointer',
}

const addBtnStyle: CSSProperties = {
  padding: '4px 8px',
  background: 'transparent',
  border: '1px dashed var(--color-separator)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--color-text-secondary)',
  cursor: 'pointer',
  textAlign: 'left',
}

const asyncNoticeStyle: CSSProperties = {
  minHeight: 72,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  flexWrap: 'wrap',
  padding: '14px 16px',
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  color: 'var(--color-text-secondary)',
  fontFamily: 'var(--font-body)',
  fontSize: 14,
}
const asyncRetryStyle: CSSProperties = {
  minHeight: 44,
  padding: '8px 12px',
  background: 'transparent',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)',
  color: 'var(--color-text-primary)',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 650,
  cursor: 'pointer',
}

const fullListStyle: CSSProperties = { background: 'var(--color-surface)', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)', overflow: 'hidden' }
const fullRowHeaderMobileStyle: CSSProperties = { display: 'grid', gridTemplateColumns: '1fr', gap: 12 }
const fullActionsMobileStyle: CSSProperties = { width: '100%', display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 6 }

const fullSummaryStyle: CSSProperties = { margin: 0, fontSize: 13, color: 'var(--color-text-secondary)' }
const fullRowHeaderStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }
const fullNameLineStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }
const fullNameStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 15, color: 'var(--color-text-primary)' }
const scheduleSentenceStyle: CSSProperties = { margin: '7px 0 0', fontSize: 14, color: 'var(--color-text-primary)' }
const actionSentenceStyle: CSSProperties = { margin: '3px 0 0', fontSize: 13, color: 'var(--color-text-secondary)' }
const lastRunStyle: CSSProperties = { margin: '7px 0 0', fontSize: 12, color: 'var(--color-text-muted)' }
const fullActionsStyle: CSSProperties = { display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }
const fullActionButtonStyle: CSSProperties = { minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px 11px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }
const fullMetaStyle: CSSProperties = { margin: 0, fontSize: 13, lineHeight: 1.45, color: 'var(--color-text-secondary)' }
const fullWhyBoxStyle: CSSProperties = { display: 'grid', gap: 5, marginTop: 12, padding: 12, background: 'var(--color-selected)', borderRadius: 'var(--r-control)' }
const fullEmptyStyle: CSSProperties = { margin: 0, padding: 16, border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)', fontSize: 13 }
const fullFormStyle: CSSProperties = { display: 'grid', gap: 10, padding: 14, background: 'var(--color-surface-elevated)', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)' }
const fullInputStyle: CSSProperties = { minHeight: 44, background: 'var(--color-surface)', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '8px 10px', fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-primary)', outline: 'none' }
const fullTypeChipStyle: CSSProperties = { minHeight: 44, padding: '8px 11px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', fontFamily: 'var(--font-body)', fontSize: 13, cursor: 'pointer' }
const fullAddButtonStyle: CSSProperties = { minHeight: 44, justifySelf: 'start', padding: '9px 13px', background: 'var(--color-accent)', border: 0, borderRadius: 'var(--r-control)', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 700, color: '#fff', cursor: 'pointer' }

function fullRowStyle(enabled: number, isLast: boolean): CSSProperties {
  return { padding: '16px 18px', background: 'var(--color-surface)', borderBottom: isLast ? 'none' : '1px solid var(--color-separator)', opacity: enabled ? 1 : 0.72 }
}

function statusPillStyle(enabled: boolean): CSSProperties {
  return { padding: '4px 8px', borderRadius: 999, background: enabled ? 'rgba(83, 150, 108, 0.10)' : 'var(--color-canvas)', color: enabled ? 'var(--color-success)' : 'var(--color-text-muted)', fontSize: 11.5, fontWeight: 650 }
}
