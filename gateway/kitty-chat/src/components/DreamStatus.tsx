'use client'
import { useState, useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { fetchDreamStatus, triggerDreamConsolidation, type DreamStatusPayload } from '@/lib/gateway'

function fmtLastRun(ts: number | null, label?: string | null): string {
  if (label) return label
  if (!ts) return 'never'
  return new Date(ts * 1000).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function DreamStatus() {
  const [status, setStatus] = useState<DreamStatusPayload | null>(null)
  const [triggering, setTriggering] = useState(false)
  const mountedRef = useRef(true)
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    mountedRef.current = true
    void loadStatus()

    return () => {
      mountedRef.current = false
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
        refreshTimeoutRef.current = null
      }
    }
  }, [])

  async function loadStatus() {
    const nextStatus = await fetchDreamStatus()
    if (!mountedRef.current) return
    setStatus(nextStatus)
  }

  async function handleTrigger() {
    if (triggering) return
    setTriggering(true)
    const ok = await triggerDreamConsolidation()
    if (ok) {
      await new Promise<void>(resolve => {
        refreshTimeoutRef.current = setTimeout(() => {
          refreshTimeoutRef.current = null
          resolve()
        }, 800)
      })
      if (!mountedRef.current) return
      await loadStatus()
    }
    if (!mountedRef.current) return
    setTriggering(false)
  }

  return (
    <div style={{ padding: '0 16px 12px', borderBottom: '1px solid var(--border)', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={sectionLabelStyle}>dream loop</span>
        <span style={countStyle}>
          {status ? status.insights_count : 0} insights
        </span>
      </div>

      {!status ? (
        <p style={emptyStyle}>consolidation unavailable</p>
      ) : (
        <>
          <div style={rowStyle}>
            <span style={metaLabelStyle}>status</span>
            <span style={{ ...metaValueStyle, color: status.never ? 'var(--text-faint)' : 'var(--mint)' }}>
              {status.never ? 'never run' : status.status}
            </span>
          </div>
          <div style={rowStyle}>
            <span style={metaLabelStyle}>last run</span>
            <span style={metaValueStyle}>{fmtLastRun(status.last_run, status.last_run_label)}</span>
          </div>
          <button
            onClick={() => void handleTrigger()}
            disabled={triggering}
            style={{ ...triggerBtnStyle, opacity: triggering ? 0.5 : 1 }}
          >
            {triggering ? 'running…' : 'run consolidation'}
          </button>
        </>
      )}
    </div>
  )
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  color: 'var(--text-ghost)',
  letterSpacing: '0.16em',
  textTransform: 'uppercase',
}

const countStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-faint)',
}

const rowStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 0',
  gap: 8,
}

const metaLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
}

const metaValueStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-dim)',
}

const triggerBtnStyle: CSSProperties = {
  marginTop: 8,
  width: '100%',
  padding: '5px 10px',
  background: 'rgba(102,119,204,0.12)',
  border: '1px solid rgba(102,119,204,0.3)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--indigo)',
  cursor: 'pointer',
  textAlign: 'left',
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
}
