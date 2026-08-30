'use client'

import type { CSSProperties } from 'react'
import type { BuilderPacketStatus, BuilderAttemptStatus } from '@/lib/gateway'

const sectionTitle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--ink-2)',
  margin: '0 0 8px 0',
}

const fieldRow: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 8,
  padding: '4px 0',
  borderBottom: '1px solid var(--line)',
}

const fieldLabel: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
  flexShrink: 0,
  minWidth: 90,
}

const fieldValue: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink)',
  wordBreak: 'break-all',
  textAlign: 'right',
}

const badgeBase: CSSProperties = {
  display: 'inline-block',
  padding: '2px 6px',
  borderRadius: 3,
  fontSize: 10,
  fontWeight: 600,
  fontFamily: 'var(--font-mono)',
}

function stateColor(state: string): string {
  switch (state) {
    case 'running': return '#4CAF50'
    case 'blocked': return '#FF9800'
    case 'failed': return '#F44336'
    case 'done': case 'completed': return '#2196F3'
    case 'review-ready': case 'awaiting_review': return '#9C27B0'
    case 'cancelled': return '#757575'
    default: return 'var(--ink-2)'
  }
}

function stateLabel(state: string): string {
  switch (state) {
    case 'review-ready': return 'review ready'
    case 'awaiting_review': return 'review needed'
    default: return state.replace(/_/g, ' ')
  }
}

function verdictColor(verdict: string | null | undefined): string {
  switch (verdict) {
    case 'approve': return '#4CAF50'
    case 'request_changes': return '#FF9800'
    case 'reject': return '#F44336'
    default: return 'var(--ink-2)'
  }
}

interface WorkerInspectorProps {
  packet: BuilderPacketStatus | null
}

export function WorkerInspector({ packet }: WorkerInspectorProps) {
  if (!packet) {
    return (
      <div style={{ padding: 16 }}>
        <p style={{ ...sectionTitle, marginBottom: 8 }}>Inspector</p>
        <p style={{ fontSize: 12, color: 'var(--ink-3)', fontFamily: 'var(--font-body)' }}>
          Select a packet to inspect.
        </p>
      </div>
    )
  }

  const run = packet.run
  const lease = packet.lease
  const pub = packet.publication
  const attempt = packet.attempt_history?.[0]
  const validation = attempt?.validation
  const review = attempt?.review

  return (
    <div style={{ padding: 12, overflow: 'auto', maxHeight: '100%' }}>
      <p style={sectionTitle}>State</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
        <span style={{ ...badgeBase, background: stateColor(packet.task_state ?? 'unknown') + '22', color: stateColor(packet.task_state ?? 'unknown') }}>
          {stateLabel(packet.task_state ?? 'unknown')}
        </span>
        {packet.failure_kind && (
          <span style={{ ...badgeBase, background: '#F4433622', color: '#F44336' }}>
            {packet.failure_kind}
          </span>
        )}
        {packet.blocked_reason && (
          <span style={{ ...badgeBase, background: '#FF980022', color: '#FF9800' }}>
            blocked
          </span>
        )}
        {packet.blocked_reason && (
          <span style={{ ...badgeBase, background: '#FF980022', color: '#FF9800' }}>
            blocked
          </span>
        )}
        {run?.state && (() => {
          const state = run.state
          return (
            <span key={state} style={{ ...badgeBase, background: stateColor(state) + '22', color: stateColor(state) }}>
              {stateLabel(state)}
            </span>
          )
        })()}
      </div>

      {lease && (
        <>
          <p style={sectionTitle}>Branch & Worktree</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>branch</span>
              <span style={fieldValue}>{lease.branch || '—'}</span>
            </div>
            <div style={fieldRow}>
              <span style={fieldLabel}>base SHA</span>
              <span style={{ ...fieldValue, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                {lease.base_sha ? lease.base_sha.slice(0, 9) + '…' : '—'}
              </span>
            </div>
            <div style={fieldRow}>
              <span style={fieldLabel}>worker</span>
              <span style={fieldValue}>{lease.worker_id || '—'}</span>
            </div>
          </div>
        </>
      )}

      {run && (
        <>
          <p style={sectionTitle}>Run</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>run ID</span>
              <span style={{ ...fieldValue, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                {run.id.slice(0, 8)}
              </span>
            </div>
            {run.started_at && (
              <div style={fieldRow}>
                <span style={fieldLabel}>started</span>
                <span style={fieldValue}>{new Date(run.started_at).toLocaleTimeString()}</span>
              </div>
            )}
            {run.last_heartbeat_at && (
              <div style={fieldRow}>
                <span style={fieldLabel}>heartbeat</span>
                <span style={fieldValue}>{new Date(run.last_heartbeat_at).toLocaleTimeString()}</span>
              </div>
            )}
            {run.exit_code !== null && (
              <div style={fieldRow}>
                <span style={fieldLabel}>exit code</span>
                <span style={{ ...fieldValue, color: run.exit_code === 0 ? '#4CAF50' : '#F44336' }}>
                  {run.exit_code}
                </span>
              </div>
            )}
          </div>
        </>
      )}

      {attempt && (
        <>
          <p style={sectionTitle}>Implementation</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>status</span>
              <span style={fieldValue}>
                {attempt.implementation_status || attempt.outcome || '—'}
              </span>
            </div>
            {attempt.implementation?.summary && (
              <div style={fieldRow}>
                <span style={fieldLabel}>summary</span>
                <span style={{ ...fieldValue, fontSize: 11 }}>
                  {attempt.implementation.summary.slice(0, 120)}
                </span>
              </div>
            )}
          </div>
        </>
      )}

      {validation && validation.status && (
        <>
          <p style={sectionTitle}>Validation</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>verdict</span>
              <span style={{ ...fieldValue, color: verdictColor(validation.status) }}>
                {validation.status}
              </span>
            </div>
            <div style={fieldRow}>
              <span style={fieldLabel}>commands</span>
              <span style={fieldValue}>
                {validation.failed_command_count}/{validation.command_count} failed
              </span>
            </div>
            {validation.summary && (
              <div style={fieldRow}>
                <span style={fieldLabel}>summary</span>
                <span style={{ ...fieldValue, fontSize: 11 }}>
                  {validation.summary.slice(0, 120)}
                </span>
              </div>
            )}
          </div>
        </>
      )}

      {review && review.verdict && (
        <>
          <p style={sectionTitle}>Review</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>verdict</span>
              <span style={{ ...fieldValue, color: verdictColor(review.verdict) }}>
                {review.verdict.replace(/_/g, ' ')}
              </span>
            </div>
            {review.summary && (
              <div style={fieldRow}>
                <span style={fieldLabel}>summary</span>
                <span style={{ ...fieldValue, fontSize: 11 }}>
                  {review.summary.slice(0, 120)}
                </span>
              </div>
            )}
            {review.findings?.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 10, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)' }}>
                {review.findings.length} finding{review.findings.length !== 1 ? 's' : ''}
              </div>
            )}
          </div>
        </>
      )}

      {pub && (
        <>
          <p style={sectionTitle}>Publication</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>PR</span>
              <span style={fieldValue}>
                {pub.pr_number ? `#${pub.pr_number}` : '—'}
              </span>
            </div>
            {pub.head_sha && (
              <div style={fieldRow}>
                <span style={fieldLabel}>head SHA</span>
                <span style={{ ...fieldValue, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                  {pub.head_sha.slice(0, 9)}…
                </span>
              </div>
            )}
            <div style={fieldRow}>
              <span style={fieldLabel}>checks</span>
              <span style={{ ...fieldValue, color: pub.checks_state === 'SUCCESS' ? '#4CAF50' : 'var(--ink-2)' }}>
                {pub.checks_state || '—'}
              </span>
            </div>
            <div style={fieldRow}>
              <span style={fieldLabel}>merged</span>
              <span style={{ ...fieldValue, color: pub.merged ? '#4CAF50' : 'var(--ink-2)' }}>
                {pub.merged ? 'yes' : 'no'}
              </span>
            </div>
          </div>
        </>
      )}

      {packet.budget.used > 0 && (
        <>
          <p style={sectionTitle}>Budget</p>
          <div style={{ marginBottom: 12 }}>
            <div style={fieldRow}>
              <span style={fieldLabel}>attempts</span>
              <span style={fieldValue}>
                {packet.budget.used}/{packet.budget.max ?? '∞'}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
