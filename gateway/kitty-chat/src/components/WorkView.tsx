'use client'

import type { CSSProperties, ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import { useWorkSnapshot, type GatewayWorkItem, type GatewayWorkState } from '@/lib/work'

const STATE_COLORS: Record<GatewayWorkState, string> = {
  active: 'var(--c-yellow)',
  paused: 'var(--ink-2)',
  failed: 'var(--c-red)',
  blocked: 'var(--c-red)',
  completed: 'var(--c-green)',
  ready: 'var(--c-blue)',
  waiting: 'var(--ink-2)',
}

export default function WorkView({ isMobile }: { isMobile: boolean; onNavigate?: (view: string) => void }) {
  const work = useWorkSnapshot()
  const snapshot = work.data

  return (
    <div style={{
      flex: 1,
      padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
      display: 'grid', gap: 20, alignContent: 'start',
    }}>
      <header style={{ display: 'grid', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Work</h1>
          {snapshot && <SourceStatus state={snapshot.source.state} observedAt={snapshot.observed_at} />}
        </div>
        <p style={{ margin: 0, color: 'var(--ink-2)' }}>
          Live Gateway projection of Builder work. No separate task state lives here.
        </p>
      </header>

      {work.isPending && <Notice>Loading work…</Notice>}
      {work.isError && (
        <Notice>
          <span>Work unavailable: {work.error instanceof Error ? work.error.message : 'Gateway request failed'}</span>
          <button type="button" onClick={() => void work.refetch()} style={retryStyle}>
            <RefreshCw size={12} /> retry
          </button>
        </Notice>
      )}

      {snapshot && (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(['active', 'blocked', 'failed', 'ready', 'waiting', 'paused', 'completed'] as GatewayWorkState[])
              .filter(state => snapshot.counts[state] > 0)
              .map(state => <Count key={state} state={state} value={snapshot.counts[state]} />)}
          </div>

          {snapshot.items.length === 0 ? (
            <Notice>No Builder work is currently projected.</Notice>
          ) : (
            <section aria-label="Gateway work items" style={{ display: 'grid', gap: 10 }}>
              {snapshot.items.map(item => <WorkRow key={item.id} item={item} />)}
            </section>
          )}
        </>
      )}
    </div>
  )
}

function Notice({ children }: { children: ReactNode }) {
  return <div style={{ border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)', padding: '14px 16px', color: 'var(--ink-2)' }}>{children}</div>
}

function Count({ state, value }: { state: GatewayWorkState; value: number }) {
  return (
    <span style={{
      border: '1px solid var(--line)', borderRadius: 999, padding: '5px 10px',
      fontFamily: 'var(--font-mono)', fontSize: 11, color: STATE_COLORS[state],
      background: 'var(--surface)',
    }}>
      {value} {state}
    </span>
  )
}

function SourceStatus({ state, observedAt }: { state: 'available' | 'degraded'; observedAt: string }) {
  const observed = new Date(observedAt)
  const time = Number.isNaN(observed.getTime())
    ? observedAt
    : observed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: state === 'available' ? 'var(--c-green)' : 'var(--c-yellow)' }}>
      <span>Builder {state}</span>
      <span style={{ color: 'var(--ink-2)' }}> · observed {time}</span>
    </span>
  )
}

function approvalLabel(item: GatewayWorkItem): string | null {
  const approval = item.evidence.approval
  if (!approval || typeof approval !== 'object') return null
  const state = (approval as Record<string, unknown>).state
  return typeof state === 'string' ? `approval ${state}` : null
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
}

const retryStyle: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  border: '1px solid var(--line)', borderRadius: 8,
  padding: '5px 9px', background: 'transparent', color: 'var(--ink)', cursor: 'pointer',
}

function WorkRow({ item }: { item: GatewayWorkItem }) {
  const approval = approvalLabel(item)
  const detail = item.blocker?.reason || item.next_action
  return (
    <article style={{
      border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)',
      padding: '14px 16px', display: 'grid', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: STATE_COLORS[item.state] }} />
        <strong style={{ color: 'var(--ink)', fontSize: 14 }}>{item.title || item.id}</strong>
        <span style={{ ...metaStyle, color: STATE_COLORS[item.state] }}>{item.state}</span>
        <span style={{ ...metaStyle, marginLeft: 'auto' }}>{item.id}</span>
      </div>
      {item.current_packet && (
        <div style={metaStyle}>
          {item.current_packet.title || item.current_packet.id || 'packet'}
          {item.current_packet.task_state ? ` · ${item.current_packet.task_state}` : ''}
        </div>
      )}
      {item.current_run && <div style={metaStyle}>run {item.current_run.state || 'unknown'} · {item.current_run.id}</div>}
      {detail && <div style={{ color: 'var(--ink-2)', fontSize: 13 }}>{detail}</div>}
      {approval && <div style={{ ...metaStyle, color: 'var(--ink-2)' }}>{approval}</div>}
    </article>
  )
}
