'use client'

import { useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { AlertTriangle, Clock3, ExternalLink, RefreshCw } from 'lucide-react'
import { useGatewayWork, useGatewayWorkDetail, useGatewayWorkEvents } from '@/lib/queries'
import type { GatewayWorkEvent, GatewayWorkItem, GatewayWorkState } from '@/lib/gateway'

const STATE: Record<GatewayWorkState, { label: string; color: string; rank: number; next: string }> = {
  review: { label: 'review', color: 'var(--c-yellow)', rank: 0, next: 'Review the evidence and decide what happens next.' },
  blocked: { label: 'blocked', color: 'var(--c-red)', rank: 1, next: 'Resolve the blocker before Builder can continue.' },
  failed: { label: 'failed', color: 'var(--c-red)', rank: 2, next: 'Inspect the failure evidence before another attempt.' },
  running: { label: 'working', color: 'var(--c-yellow)', rank: 3, next: 'Builder is working; watch evidence and events.' },
  pending: { label: 'pending', color: 'var(--c-blue)', rank: 4, next: 'Waiting for Builder to start this work.' },
  cancelled: { label: 'cancelled', color: 'var(--ink-2)', rank: 5, next: 'This work has been cancelled.' },
  completed: { label: 'completed', color: 'var(--c-green)', rank: 6, next: 'Verified work is complete.' },
}

type Props = { isMobile: boolean; onNavigate?: (view: string) => void }

export default function WorkView({ isMobile, onNavigate }: Props) {
  const work = useGatewayWork()
  const snapshot = work.data
  const sorted = useMemo(() => [...(snapshot?.items ?? [])].sort((a, b) => {
    const byState = STATE[a.state].rank - STATE[b.state].rank
    return byState || (b.priority ?? 0) - (a.priority ?? 0) || a.title.localeCompare(b.title)
  }), [snapshot?.items])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const activeId = selectedId && snapshot?.items.some(item => item.work_id === selectedId)
    ? selectedId
    : sorted[0]?.work_id ?? null
  const detail = useGatewayWorkDetail(activeId)
  const events = useGatewayWorkEvents(activeId)
  const stale = Boolean(snapshot && Date.parse(snapshot.valid_until) < Date.now())
  const degraded = Boolean(snapshot && snapshot.source_health.state !== 'available')

  return (
    <div style={{
      flex: 1,
      padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
      display: 'grid', gap: 18, alignContent: 'start', minWidth: 0,
    }}>
      <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'grid', gap: 5 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Work</h1>
          <p style={{ margin: 0, color: 'var(--ink-2)', maxWidth: 680 }}>
            Gateway projects Builder truth here. This page does not keep a second task queue or approval state.
          </p>
        </div>
        <button type="button" onClick={() => onNavigate?.('builder')} style={secondaryButton}>
          Builder diagnostics <ExternalLink size={13} />
        </button>
      </header>

      {work.isPending && <Notice>Loading authoritative work…</Notice>}
      {work.isError && (
        <Notice tone="danger">
          <strong>Work unavailable.</strong> {messageOf(work.error)}
          <button type="button" onClick={() => void work.refetch()} style={refreshButton}><RefreshCw size={12} /> refresh status</button>
        </Notice>
      )}
      {snapshot && degraded && (
        <Notice tone="warning">
          <AlertTriangle size={14} /> Builder source is {snapshot.source_health.state}.
          {snapshot.source_health.reason ? ` ${snapshot.source_health.reason}` : ''} Showing the last truthful projection.
        </Notice>
      )}
      {snapshot && stale && (
        <Notice tone="warning">
          <Clock3 size={14} /> Work data is stale as of {formatTime(snapshot.valid_until)}. Showing it instead of pretending it is fresh.
        </Notice>
      )}

      {snapshot && (
        <>
          <section aria-label="Work state counts" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(Object.keys(STATE) as GatewayWorkState[])
              .filter(state => (snapshot.state_counts[state] ?? 0) > 0)
              .map(state => <Count key={state} state={state} value={snapshot.state_counts[state] ?? 0} />)}
            <span style={{ ...meta, marginLeft: 'auto', alignSelf: 'center' }}>
              {snapshot.total_items} total · observed {formatTime(snapshot.observed_at)}
            </span>
          </section>

          {snapshot.items.length === 0 ? (
            <Notice>No Builder work matches this projection.</Notice>
          ) : (
            <div style={{
              display: 'grid', gap: 14,
              gridTemplateColumns: isMobile ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) minmax(320px, .82fr)',
              alignItems: 'start', minWidth: 0,
            }}>
              <section aria-label="Authoritative work items" style={{ display: 'grid', gap: 9, minWidth: 0 }}>
                {sorted.map(item => (
                  <WorkCard key={item.work_id} item={item} selected={item.work_id === activeId} onSelect={() => setSelectedId(item.work_id)} />
                ))}
              </section>
              <DetailPanel item={detail.data ?? null} loading={detail.isPending && Boolean(activeId)} error={detail.error} events={events.data?.events ?? []} eventsError={events.error} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
function WorkCard({ item, selected, onSelect }: { item: GatewayWorkItem; selected: boolean; onSelect: () => void }) {
  const cfg = STATE[item.state]
  const problem = item.blocker || item.error
  return (
    <button type="button" onClick={onSelect} aria-pressed={selected} style={{
      width: '100%', textAlign: 'left', cursor: 'pointer', color: 'inherit',
      border: `1px solid ${selected ? cfg.color : 'var(--line)'}`,
      borderRadius: 12, background: selected ? 'var(--surface-2)' : 'var(--surface)',
      padding: '13px 14px', display: 'grid', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span aria-hidden style={{ width: 7, height: 7, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
        <strong style={{ color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.title || item.work_id}</strong>
        <span style={{ ...meta, color: cfg.color, marginLeft: 'auto' }}>{cfg.label}</span>
      </div>
      {item.summary && <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.45 }}>{item.summary}</div>}
      {problem && <div style={{ fontSize: 12, color: 'var(--c-red)' }}>{problem}</div>}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <span style={meta}>source {item.source_state}</span>
        <span style={meta}>{cfg.next}</span>
      </div>
    </button>
  )
}

function DetailPanel({ item, loading, error, events, eventsError }: {
  item: GatewayWorkItem | null
  loading: boolean
  error: unknown
  events: GatewayWorkEvent[]
  eventsError: unknown
}) {
  if (loading) return <Panel><span style={{ color: 'var(--ink-2)' }}>Loading work detail…</span></Panel>
  if (error) return <Panel><strong>Detail unavailable.</strong><div style={{ color: 'var(--ink-2)' }}>{messageOf(error)}</div></Panel>
  if (!item) return <Panel><span style={{ color: 'var(--ink-2)' }}>Select work to inspect evidence.</span></Panel>
  const approval = item.evidence?.approval
  const evidence = item.evidence ?? {}
  return (
    <Panel>
      <div style={{ display: 'grid', gap: 4 }}>
        <span style={{ ...meta, color: STATE[item.state].color }}>{STATE[item.state].label}</span>
        <h2 style={{ margin: 0, fontSize: 18, color: 'var(--ink)' }}>{item.title || item.work_id}</h2>
        <span style={meta}>{item.work_id} · Builder {item.source_state}</span>
      </div>

      {(item.blocker || item.error) && (
        <div style={{ borderLeft: '3px solid var(--c-red)', paddingLeft: 10, color: 'var(--ink)' }}>
          {item.blocker || item.error}
        </div>
      )}

      <Evidence label="Approval">
        {approval ? `${approval.state}${approval.reason ? ` — ${approval.reason}` : ''}` : 'unavailable — no Gateway approval evidence'}
      </Evidence>
      {evidence.implementation !== undefined && <Evidence label="Implementation">{summarize(evidence.implementation)}</Evidence>}
      {evidence.validation !== undefined && <Evidence label="Validation">{summarize(evidence.validation)}</Evidence>}
      {evidence.review !== undefined && <Evidence label="Review">{summarize(evidence.review)}</Evidence>}
      {evidence.publication !== undefined && <Evidence label="Publication">{summarize(evidence.publication)}</Evidence>}
      {item.latest_run && <Evidence label="Latest run">{summarize(item.latest_run)}</Evidence>}

      <div style={{ display: 'grid', gap: 8 }}>
        <strong style={{ fontSize: 12, color: 'var(--ink)' }}>Recent events</strong>
        {Boolean(eventsError) && <span style={{ color: 'var(--c-red)', fontSize: 12 }}>Events unavailable: {messageOf(eventsError)}</span>}
        {!eventsError && events.length === 0 && <span style={{ ...meta }}>No persisted events.</span>}
        {!eventsError && events.slice(-8).map((event, index) => <EventRow key={String(event.id ?? index)} event={event} />)}
      </div>
    </Panel>
  )
}

function EventRow({ event }: { event: GatewayWorkEvent }) {
  const label = String(event.event_type ?? event.type ?? 'event')
  const time = String(event.created_at ?? event.timestamp ?? '')
  return (
    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 7, display: 'grid', gap: 2 }}>
      <span style={{ fontSize: 12, color: 'var(--ink)' }}>{label}</span>
      {time && <span style={meta}>{formatTime(time)}</span>}
    </div>
  )
}
function Evidence({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'grid', gap: 3 }}>
      <strong style={{ fontSize: 11, color: 'var(--ink-2)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</strong>
      <div style={{ fontSize: 12, color: 'var(--ink)', lineHeight: 1.45, overflowWrap: 'anywhere' }}>{children}</div>
    </div>
  )
}

function Count({ state, value }: { state: GatewayWorkState; value: number }) {
  const cfg = STATE[state]
  return (
    <span style={{ border: '1px solid var(--line)', borderRadius: 999, padding: '5px 9px', background: 'var(--surface)', ...meta, color: cfg.color }}>
      {value} {cfg.label}
    </span>
  )
}

function Panel({ children }: { children: ReactNode }) {
  return <aside style={{ border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)', padding: 15, display: 'grid', gap: 13, minWidth: 0 }}>{children}</aside>
}

function Notice({ children, tone = 'normal' }: { children: ReactNode; tone?: 'normal' | 'warning' | 'danger' }) {
  const color = tone === 'danger' ? 'var(--c-red)' : tone === 'warning' ? 'var(--c-yellow)' : 'var(--ink-2)'
  return <div style={{ border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)', padding: '12px 14px', color, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>{children}</div>
}

function summarize(value: unknown): string {
  if (value == null) return 'unavailable'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>
    for (const key of ['summary', 'status', 'verdict', 'state', 'outcome']) {
      if (typeof record[key] === 'string' && record[key]) return String(record[key])
    }
    return JSON.stringify(value)
  }
  return String(value)
}
function messageOf(value: unknown): string {
  return value instanceof Error ? value.message : String(value || 'Gateway request failed')
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const meta: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
}

const secondaryButton: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  border: '1px solid var(--line)', borderRadius: 9, padding: '7px 10px',
  background: 'var(--surface)', color: 'var(--ink)', cursor: 'pointer',
  fontSize: 12,
}

const refreshButton: CSSProperties = {
  ...secondaryButton,
  marginLeft: 'auto',
  padding: '5px 8px',
}
