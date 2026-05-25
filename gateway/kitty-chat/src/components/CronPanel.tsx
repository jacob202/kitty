'use client'
import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import {
  fetchCronSchedules, fetchCronActions, createCronSchedule,
  deleteCronSchedule, toggleCronSchedule,
  type CronSchedule, type CronScheduleType,
} from '@/lib/gateway'

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

export function CronPanel() {
  const [schedules, setSchedules] = useState<CronSchedule[]>([])
  const [actions, setActions] = useState<string[]>([])
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [action, setAction] = useState('')
  const [schedType, setSchedType] = useState<CronScheduleType>('daily')
  const [schedVal, setSchedVal] = useState('07:00')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    const [s, a] = await Promise.all([fetchCronSchedules(), fetchCronActions()])
    setSchedules(s)
    setActions(a)
    if (!action && a.length > 0) setAction(a[0])
  }

  async function handleAdd() {
    if (!name.trim() || !action || !schedVal.trim() || saving) return
    setSaving(true)
    const id = await createCronSchedule(name.trim(), action, schedType, schedVal.trim())
    setSaving(false)
    if (id) {
      setName(''); setSchedVal(valuePlaceholder(schedType)); setAdding(false)
      await load()
    }
  }

  async function handleDelete(id: string) {
    await deleteCronSchedule(id)
    await load()
  }

  async function handleToggle(id: string) {
    await toggleCronSchedule(id)
    await load()
  }

  function handleTypeChange(t: CronScheduleType) {
    setSchedType(t)
    setSchedVal(valuePlaceholder(t))
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {/* Schedule list */}
      {schedules.length > 0 ? (
        <div style={{ display: 'grid', gap: 4 }}>
          {schedules.map(s => (
            <div key={s.id} style={rowStyle(s.enabled)}>
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
                  <button
                    onClick={() => void handleToggle(s.id)}
                    style={{ ...toggleBtnStyle, color: s.enabled ? 'var(--teal)' : 'var(--text-faint)' }}
                    title={s.enabled ? 'disable' : 'enable'}
                  >
                    {s.enabled ? 'On' : 'Off'}
                  </button>
                  <button
                    onClick={() => void handleDelete(s.id)}
                    style={deleteBtnStyle}
                    title="delete"
                  >
                    Del
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={emptyStyle}>no schedules yet</p>
      )}

      {/* Add form */}
      {adding ? (
        <div style={formStyle}>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="name"
            style={inputStyle}
          />
          {actions.length > 0 ? (
            <select value={action} onChange={e => setAction(e.target.value)} style={inputStyle}>
              {actions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          ) : (
            <input
              value={action}
              onChange={e => setAction(e.target.value)}
              placeholder="action name"
              style={inputStyle}
            />
          )}
          <div style={{ display: 'flex', gap: 4 }}>
            {(['daily', 'interval', 'once'] as CronScheduleType[]).map(t => (
              <button
                key={t}
                onClick={() => handleTypeChange(t)}
                style={{
                  ...typeChipStyle,
                  background: schedType === t ? 'rgba(102,119,204,0.16)' : 'transparent',
                  color: schedType === t ? 'var(--indigo)' : 'var(--text-muted)',
                  borderColor: schedType === t ? 'rgba(102,119,204,0.35)' : 'var(--border-dim)',
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
            style={inputStyle}
          />
          <div style={{ display: 'flex', gap: 5 }}>
            <button
              onClick={() => void handleAdd()}
              disabled={!name.trim() || !action || !schedVal.trim() || saving}
              style={{ ...saveBtnStyle, flex: 1, opacity: !name.trim() || saving ? 0.4 : 1 }}
            >
              {saving ? 'saving…' : 'save'}
            </button>
            <button onClick={() => setAdding(false)} style={cancelBtnStyle}>cancel</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} style={addBtnStyle}>+ add schedule</button>
      )}
    </div>
  )
}

function rowStyle(enabled: number): CSSProperties {
  return {
    padding: '5px 7px',
    background: enabled ? 'var(--recessed)' : 'transparent',
    border: `1px solid ${enabled ? 'var(--border-dim)' : 'var(--border-dim)'}`,
    borderRadius: 5,
    opacity: enabled ? 1 : 0.5,
  }
}

function typeBadgeStyle(type: string): CSSProperties {
  const color = type === 'daily' ? 'var(--teal)'
    : type === 'interval' ? 'var(--indigo)'
    : 'var(--orange-2)'
  return { fontFamily: 'var(--font-mono)', fontSize: 9, color, textTransform: 'uppercase', letterSpacing: '0.06em' }
}

const nameStyle: CSSProperties = {
  margin: '0 0 2px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
}

const metaStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-faint)',
}

const toggleBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontSize: 11,
  padding: '1px 3px',
  lineHeight: 1,
}

const deleteBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--text-faint)',
  cursor: 'pointer',
  fontSize: 13,
  padding: '1px 3px',
  lineHeight: 1,
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
}

const formStyle: CSSProperties = {
  display: 'grid',
  gap: 5,
  padding: '8px 10px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 6,
}

const inputStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border-dim)',
  borderRadius: 4,
  padding: '4px 7px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
}

const typeChipStyle: CSSProperties = {
  padding: '2px 7px',
  border: '1px solid var(--border-dim)',
  borderRadius: 10,
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  cursor: 'pointer',
}

const saveBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'rgba(102,119,204,0.12)',
  border: '1px solid rgba(102,119,204,0.3)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--indigo)',
  cursor: 'pointer',
}

const cancelBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'transparent',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
  cursor: 'pointer',
}

const addBtnStyle: CSSProperties = {
  padding: '4px 8px',
  background: 'transparent',
  border: '1px dashed var(--border-dim)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
  cursor: 'pointer',
  textAlign: 'left',
}
