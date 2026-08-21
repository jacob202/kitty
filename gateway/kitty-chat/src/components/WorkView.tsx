'use client'

import type { CSSProperties, ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import { useWorkSnapshot, type GatewayWorkItem, type GatewayWorkState } from '@/lib/work'

type WorkGroup = 'needs-you' | 'in-progress' | 'completed'

const GROUP_LABELS: Record<WorkGroup, string> = {
  'needs-you': 'Needs you',
  'in-progress': 'In progress',
  completed: 'Completed',
}

const STATE_COLORS: Record<GatewayWorkState, string> = {
  active: 'var(--c-yellow)', paused: 'var(--ink-2)', failed: 'var(--c-red)',
  blocked: 'var(--c-red)', completed: 'var(--c-green)', ready: 'var(--c-blue)', waiting: 'var(--ink-2)',
}

export default function WorkView({ isMobile }: { isMobile: boolean; onNavigate?: (view: string) => void }) {
  const work = useWorkSnapshot()
  const snapshot = work.data
  const sourceLabel = snapshot && isExpired(snapshot.valid_until) ? 'stale' : snapshot?.source.state

  return (
    <div style={{ flex: 1, padding: isMobile ? '16px 12px 124px' : '24px 32px 40px', display: 'grid', gap: 20, alignContent: 'start' }}>
      <header style={{ display: 'grid', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Work</h1>
          {snapshot && sourceLabel && <SourceStatus state={sourceLabel} observedAt={snapshot.observed_at} />}
        </div>
        <p style={{ margin: 0, color: 'var(--ink-2)' }}>Live Gateway projection of Builder work. No separate task state lives here.</p>
      </header>

      {work.isPending && <Notice>Loading work…</Notice>}
      {work.isError && (
        <Notice>
          <span>Work unavailable: {work.error instanceof Error ? work.error.message : 'Gateway request failed'}</span>
          <button type="button" onClick={() => void work.refetch()} style={retryStyle}><RefreshCw size={12} /> retry</button>
        </Notice>
      )}

      {snapshot && (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(['active', 'blocked', 'failed', 'ready', 'waiting', 'paused', 'completed'] as GatewayWorkState[])
              .filter(state => snapshot.counts[state] > 0)
              .map(state => <Count key={state} state={state} value={snapshot.counts[state]} />)}
          </div>
          {snapshot.total_items > snapshot.items.length && (
            <div style={metaStyle}>Showing {snapshot.items.length} of {snapshot.total_items} most relevant items.</div>
          )}
          {snapshot.items.length === 0 ? <Notice>No Builder work is currently projected.</Notice> : (
            <div style={{ display: 'grid', gap: 18 }}>
              {(['needs-you', 'in-progress', 'completed'] as WorkGroup[]).map(group => {
                const items = snapshot.items.filter(item => workGroup(item.state) === group)
                if (items.length === 0) return null
                const label = GROUP_LABELS[group]
                return (
                  <section key={group} aria-label={label} style={{ display: 'grid', gap: 10 }}>
                    <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--ink)' }}>{label}</h2>
                    {items.map(item => <WorkRow key={item.id} item={item} />)}
                  </section>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function workGroup(state: GatewayWorkState): WorkGroup {
  if (state === 'blocked' || state === 'failed' || state === 'paused') return 'needs-you'
  if (state === 'completed') return 'completed'
  return 'in-progress'
}

function isExpired(validUntil: string): boolean {
  const expiry = Date.parse(validUntil)
  return !Number.isFinite(expiry) || expiry <= Date.now()
}

function Notice({ children }: { children: ReactNode }) {
  return <div style={{ border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)', padding: '14px 16px', color: 'var(--ink-2)' }}>{children}</div>
}

function Count({ state, value }: { state: GatewayWorkState; value: number }) {
  return <span style={{ border: '1px solid var(--line)', borderRadius: 999, padding: '5px 10px', fontFamily: 'var(--font-mono)', fontSize: 11, color: STATE_COLORS[state], background: 'var(--surface)' }}>{value} {state}</span>
}

function SourceStatus({ state, observedAt }: { state: 'available' | 'degraded' | 'stale'; observedAt: string }) {
  const observed = new Date(observedAt)
  const time = Number.isNaN(observed.getTime()) ? observedAt : observed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: state === 'available' ? 'var(--c-green)' : 'var(--c-yellow)' }}><span>Builder {state}</span><span style={{ color: 'var(--ink-2)' }}> · observed {time}</span></span>
}

function approvalLabel(item: GatewayWorkItem): string | null {
  const approval = item.evidence.approval
  if (!approval || typeof approval !== 'object') return null
  const state = (approval as Record<string, unknown>).state
  return typeof state === 'string' ? `approval ${state}` : null
}

const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }
const retryStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 5, border: '1px solid var(--line)', borderRadius: 8, padding: '5px 9px', background: 'transparent', color: 'var(--ink)', cursor: 'pointer' }

function WorkRow({ item }: { item: GatewayWorkItem }) {
  const approval = approvalLabel(item)
  const detail = item.blocker?.reason || item.next_action
  const evidence = evidenceLabels(item)
  return (
    <article style={{ border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)', padding: '14px 16px', display: 'grid', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: STATE_COLORS[item.state] }} />
        <strong style={{ color: 'var(--ink)', fontSize: 14 }}>{item.title || item.id}</strong>
        <span style={{ ...metaStyle, color: STATE_COLORS[item.state] }}>{item.state}</span>
      </div>
      {detail && <div style={{ color: 'var(--ink-2)', fontSize: 13 }}>{detail}</div>}
      {evidence.map(label => <div key={label} style={metaStyle}>{label}</div>)}
      <details style={metaStyle}>
        <summary style={{ cursor: 'pointer', color: 'var(--ink)' }}>Details</summary>
        <div style={{ display: 'grid', gap: 4, marginTop: 6 }}>
          <div>initiative <span>{item.id}</span></div>
          {item.current_packet?.id && <div>packet <span>{item.current_packet.id}</span></div>}
          {item.current_packet?.task_id && <div>task <span>{item.current_packet.task_id}</span></div>}
          {item.current_run?.id && <div>run <span>{item.current_run.id}</span></div>}
          {item.current_packet?.task_state && <div>task state {item.current_packet.task_state}</div>}
          {approval && <div>{approval}</div>}
          {item.data_quality.issues?.map(issue => <div key={issue}>quality: {issue}</div>)}
        </div>
      </details>
    </article>
  )
}

function evidenceLabels(item: GatewayWorkItem): string[] {
  const labels: string[] = []
  if (item.evidence.review) labels.push('Review evidence available')
  if (item.evidence.publication) labels.push('Publication evidence available')
  if (item.evidence.validation) labels.push('Validation evidence available')
  return labels
}
