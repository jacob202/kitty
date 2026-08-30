'use client'
import { useState, useEffect } from 'react'
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

  useEffect(() => {
    void loadStatus()
  }, [])

  async function loadStatus() {
    try {
      setStatus(await fetchDreamStatus())
    } catch {
      setStatus(null)
    }
  }

  async function handleTrigger() {
    if (triggering) return
    setTriggering(true)
    try {
      const ok = await triggerDreamConsolidation()
      if (ok) {
        await new Promise(resolve => setTimeout(resolve, 800))
        await loadStatus()
      }
    } catch {
      // gateway unreachable — leave status unchanged
    }
    setTriggering(false)
  }

  return (
    <div style={{ padding: '0 16px 12px', borderBottom: '1px solid var(--line)', marginBottom: 12 }}>
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
            <span style={{ ...metaValueStyle, color: status.never ? 'var(--ink-2)' : 'var(--c-green)' }}>
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
  color: 'var(--ink-2)',
  letterSpacing: '0.16em',
  textTransform: 'lowercase',
}

const countStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--ink-2)',
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
  color: 'var(--ink-2)',
  textTransform: 'lowercase',
  letterSpacing: '0.06em',
}

const metaValueStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const triggerBtnStyle: CSSProperties = {
  marginTop: 8,
  width: '100%',
  padding: '5px 10px',
  background: 'rgba(102,119,204,0.12)',
  border: '1px solid rgba(102,119,204,0.3)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--c-purple)',
  cursor: 'pointer',
  textAlign: 'left',
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}
