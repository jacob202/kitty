'use client'

import type { CSSProperties } from 'react'
import { Check, Play, ShieldAlert, X } from 'lucide-react'

import { describeFailure } from '@/lib/failure-copy'
import { useAction, useApproveAction, useExecuteAction, useRejectAction } from '@/lib/queries'

export function ActionCard({ actionId }: { actionId: number }) {
  const action = useAction(actionId)
  const approve = useApproveAction()
  const reject = useRejectAction()
  const execute = useExecuteAction()

  if (action.isLoading) return <div style={cardStyle}>Loading action…</div>
  if (action.isError || !action.data) {
    return <div role="alert" style={cardStyle}>Action unavailable — {describeFailure(action.error)}</div>
  }

  const item = action.data
  const busy = approve.isPending || reject.isPending || execute.isPending
  const canApprove = item.status === 'proposed' && item.risk_tier === 'T2'
  const canRun = item.status === 'approved' || (item.status === 'proposed' && item.risk_tier !== 'T2')
  const terminal = ['executed', 'failed', 'rejected', 'outcome_unknown'].includes(item.status)

  return (
    <section aria-label={`Action: ${item.title}`} style={cardStyle}>
      <div style={headerStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={eyebrowStyle}>action · {item.kind}</div>
          <div style={titleStyle}>{item.title}</div>
          <p style={previewStyle}>{item.preview}</p>
        </div>
        <span style={tierStyle}><ShieldAlert size={12} /> {item.risk_tier}</span>
      </div>

      <div style={statusRowStyle}>
        <span style={statusStyle(item.status)}>{humanize(item.status)}</span>
        <span style={mutedStyle}>authoritative ActionQueue state</span>
      </div>

      <details style={detailsStyle}>
        <summary style={summaryStyle}>Exact payload</summary>
        <pre style={payloadStyle}>{JSON.stringify(item.payload, null, 2)}</pre>
      </details>

      {item.result && <div style={resultStyle}>{item.result}</div>}

      {!terminal && (canApprove || canRun) && (
        <div style={actionsStyle}>
          {canApprove && (
            <>
              <button aria-label="Approve action" disabled={busy} onClick={() => approve.mutate(item.id)} style={primaryButtonStyle}>
                <Check size={14} /> Approve
              </button>
              <button aria-label="Reject action" disabled={busy} onClick={() => reject.mutate(item.id)} style={secondaryButtonStyle}>
                <X size={14} /> Reject
              </button>
            </>
          )}
          {canRun && (
            <button aria-label="Run approved action" disabled={busy} onClick={() => execute.mutate(item.id)} style={primaryButtonStyle}>
              <Play size={14} /> Run
            </button>
          )}
        </div>
      )}
      {item.status === 'executing' && <div style={mutedStyle}>Running…</div>}
    </section>
  )
}

function humanize(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/^./, char => char.toUpperCase())
}

function statusStyle(status: string): CSSProperties {
  const color = status === 'executed' ? 'var(--color-success)'
    : status === 'failed' || status === 'outcome_unknown' ? 'var(--color-destructive)'
      : status === 'proposed' ? 'var(--color-warning)' : 'var(--color-text-secondary)'
  return { fontSize: 12, fontWeight: 700, color }
}

const cardStyle: CSSProperties = { margin: '10px 0', border: '1px solid var(--color-separator)', borderRadius: 12, background: 'var(--color-surface)', padding: 14, display: 'grid', gap: 12, minWidth: 0 }
const headerStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }
const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }
const titleStyle: CSSProperties = { marginTop: 3, fontSize: 15, fontWeight: 750, color: 'var(--color-text-primary)' }
const previewStyle: CSSProperties = { margin: '5px 0 0', fontSize: 12.5, lineHeight: 1.45, color: 'var(--color-text-secondary)' }
const tierStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 4, flexShrink: 0, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-warning)' }
const statusRowStyle: CSSProperties = { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }
const mutedStyle: CSSProperties = { fontSize: 11, color: 'var(--color-text-secondary)' }
const detailsStyle: CSSProperties = { borderTop: '1px solid var(--color-separator)', paddingTop: 8 }
const summaryStyle: CSSProperties = { cursor: 'pointer', minHeight: 32, display: 'inline-flex', alignItems: 'center', fontSize: 11.5, fontWeight: 650, color: 'var(--color-text-secondary)' }
const payloadStyle: CSSProperties = { margin: '6px 0 0', padding: 10, borderRadius: 8, background: 'var(--color-surface-elevated)', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontFamily: 'var(--font-mono)', fontSize: 10.5, lineHeight: 1.5, color: 'var(--color-text-primary)' }
const resultStyle: CSSProperties = { padding: 10, borderRadius: 8, background: 'var(--color-surface-elevated)', fontSize: 12.5, lineHeight: 1.45, color: 'var(--color-text-primary)' }
const actionsStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap' }
const primaryButtonStyle: CSSProperties = { minHeight: 44, border: 'none', borderRadius: 9, padding: '8px 13px', background: 'var(--color-accent)', color: 'var(--on-accent)', display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontWeight: 700 }
const secondaryButtonStyle: CSSProperties = { minHeight: 44, border: '1px solid var(--color-separator)', borderRadius: 9, padding: '8px 13px', background: 'var(--color-surface)', color: 'var(--color-text-primary)', display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontWeight: 650 }
