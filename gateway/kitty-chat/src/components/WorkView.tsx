'use client'

import { useState, type CSSProperties, type ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  useBuilderAction,
  usePreflight,
  useSupervisor,
  useWorkSnapshot,
  type BuilderCommand,
  type GatewayPreflightResult,
  type GatewaySupervisor,
  type GatewayWorkItem,
  type GatewayWorkState,
} from '@/lib/work'

type WorkGroup = 'needs-you' | 'in-progress' | 'completed'

const GROUP_LABELS: Record<WorkGroup, string> = {
  'needs-you': 'Needs you',
  'in-progress': 'In progress',
  completed: 'Completed',
}

const STATE_COLORS: Record<GatewayWorkState, string> = {
  active: 'var(--color-warning)', paused: 'var(--color-text-muted)', failed: 'var(--color-destructive)',
  blocked: 'var(--color-destructive)', completed: 'var(--color-success)', ready: 'var(--color-accent)', waiting: 'var(--color-text-muted)',
}

const INITIAL_GROUP_ITEMS = 5

export default function WorkView({
  isMobile,
  onNavigate,
}: {
  isMobile: boolean
  onNavigate?: (view: string) => void
}) {
  const work = useWorkSnapshot()
  const supervisor = useSupervisor()
  const snapshot = work.data
  const builderRunning = supervisor.data?.running ?? false
  const sourceLabel = snapshot && isExpired(snapshot.valid_until) ? 'stale' : snapshot?.source.state
  const sourceReason = snapshot?.source.state === 'degraded' ? boundedSourceReason(snapshot.source.reason) : null

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '16px 12px 124px' : '24px 32px 40px' }}>
      <div style={workCanvasStyle}>
        <header style={{ display: 'grid', gap: 10 }}>
          <div style={workHeaderStyle}>
            <div style={{ display: 'grid', gap: 5 }}>
              <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: isMobile ? 28 : 32, color: 'var(--color-text-primary)' }}>Work</h1>
              <p style={{ margin: 0, color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.5 }}>
                What is moving, blocked, and finished in Builder.
              </p>
            </div>
            <div style={workHeaderActionsStyle}>
              {snapshot && sourceLabel && <SourceStatus state={sourceLabel} observedAt={snapshot.observed_at} />}
              {onNavigate && (
                <button
                  type="button"
                  aria-label="Open Builder details"
                  onClick={() => onNavigate('builder-details')}
                  style={secondaryActionStyle}
                >
                  Builder details
                </button>
              )}
            </div>
          </div>
          {sourceReason && <DegradedSourceNotice reason={sourceReason} />}
          {supervisor.data && <BuilderRunBanner supervisor={supervisor.data} />}
        </header>

        {work.isPending && <Notice>Loading work…</Notice>}
        {work.isError && (
          <Notice>
            <div style={{ display: 'grid', gap: 8 }}>
              <span>Work is unavailable right now. Retry to reconnect to Builder.</span>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <button type="button" onClick={() => void work.refetch()} style={retryStyle}><RefreshCw size={14} /> retry</button>
                <details style={metaStyle}>
                  <summary style={{ cursor: 'pointer', color: 'var(--color-text-primary)' }}>Technical details</summary>
                  <div style={{ marginTop: 4 }}>
                    {work.error instanceof Error ? work.error.message : 'Gateway request failed'}
                  </div>
                </details>
              </div>
            </div>
          </Notice>
        )}

        {snapshot && (
          <>
            <div style={countStripStyle} aria-label="Work status summary">
              {(['active', 'blocked', 'failed', 'ready', 'waiting', 'paused', 'completed'] as GatewayWorkState[])
                .filter(state => snapshot.counts[state] > 0)
                .map(state => <Count key={state} state={state} value={snapshot.counts[state]} />)}
            </div>
            {snapshot.total_items > snapshot.items.length && (
              <div style={summaryMetaStyle}>Showing {snapshot.items.length} of {snapshot.total_items} most relevant items from Builder.</div>
            )}
            {(snapshot.historical_items ?? 0) > 0 && (
              <div style={summaryMetaStyle}>{snapshot.historical_items} historical Builder initiatives hidden from current work.</div>
            )}
            {snapshot.items.length === 0 ? <Notice>No Builder work is currently projected.</Notice> : (
              <div style={{ display: 'grid', gap: 22 }}>
                {(['needs-you', 'in-progress', 'completed'] as WorkGroup[]).map(group => {
                  const items = snapshot.items.filter(item => workGroup(item) === group)
                  if (items.length === 0) return null
                  return <WorkGroupSection key={group} group={group} items={items} builderRunning={builderRunning} />
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function WorkGroupSection({ group, items, builderRunning }: { group: WorkGroup; items: GatewayWorkItem[]; builderRunning: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const visibleItems = expanded ? items : items.slice(0, INITIAL_GROUP_ITEMS)
  const remaining = items.length - visibleItems.length
  const label = GROUP_LABELS[group]

  return (
    <section aria-label={label} style={{ display: 'grid', gap: 10 }}>
      <div style={groupHeaderStyle}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--color-text-primary)' }}>{label}</h2>
        <span style={groupCountStyle}>{items.length}</span>
      </div>
      <div data-testid="work-group-list" style={groupListStyle}>
        {visibleItems.map((item, index) => (
          <WorkRow key={item.id} item={item} isLast={index === visibleItems.length - 1} builderRunning={builderRunning} />
        ))}
      </div>
      {items.length > INITIAL_GROUP_ITEMS && (
        <button
          type="button"
          onClick={() => setExpanded(open => !open)}
          style={showMoreStyle}
        >
          {expanded ? 'Show fewer' : `Show ${remaining} more`}
        </button>
      )}
    </section>
  )
}

function DegradedSourceNotice({ reason }: { reason: string }) {
  return (
    <div style={degradedNoticeStyle}>
      <div><strong>Builder data is partial.</strong> Some work may be missing.</div>
      <details style={sourceDetailsStyle}>
        <summary style={{ cursor: 'pointer' }}>Source details</summary>
        <div style={{ marginTop: 5 }}>{reason}</div>
      </details>
    </div>
  )
}

function workGroup(item: GatewayWorkItem): WorkGroup {
  if (item.state === 'completed' || item.next_action === 'cancelled' || item.next_action === 'done') return 'completed'
  if (item.state === 'blocked' || item.state === 'failed' || item.state === 'paused') return 'needs-you'
  return 'in-progress'
}

function isExpired(validUntil: string): boolean {
  const expiry = Date.parse(validUntil)
  return !Number.isFinite(expiry) || expiry <= Date.now()
}

function boundedSourceReason(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const reason = value.trim()
  if (!reason) return null
  return reason.length <= 240 ? reason : `${reason.slice(0, 239).trimEnd()}…`
}

function Notice({ children }: { children: ReactNode }) {
  return <div style={noticeStyle}>{children}</div>
}

function Count({ state, value }: { state: GatewayWorkState; value: number }) {
  return <span style={{ ...countStyle, color: STATE_COLORS[state] }}>{value} {state}</span>
}

function SourceStatus({ state, observedAt }: { state: 'available' | 'degraded' | 'stale'; observedAt: string }) {
  const observed = new Date(observedAt)
  const time = Number.isNaN(observed.getTime()) ? observedAt : observed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <span style={{ ...sourceStatusStyle, color: state === 'available' ? 'var(--color-success)' : 'var(--color-warning)' }}>
      <span>Builder {state}</span>
      <span style={{ color: 'var(--color-text-muted)' }}> · observed {time}</span>
    </span>
  )
}

function approvalLabel(item: GatewayWorkItem): string | null {
  const approval = item.evidence.approval
  if (!approval || typeof approval !== 'object') return null
  const state = (approval as Record<string, unknown>).state
  return typeof state === 'string' ? `approval ${state}` : null
}

function PreflightBanner({ item }: { item: GatewayWorkItem }) {
  const initiativeId = item.source.initiative_id
  const packetId = item.current_packet?.id ?? item.source.packet_id
  const preflight = usePreflight(
    item.next_action === 'claim' ? initiativeId : null,
    item.next_action === 'claim' ? packetId : null,
  )

  if (!preflight.data) return null
  const pf = preflight.data

  // Only show for non-free routes or when there is a blocking reason.
  const hasBlockingReasons = pf.reasons.length > 0
  const isPaid = pf.route !== null && pf.route !== 'free'
  if (!hasBlockingReasons && !isPaid) return null

  return (
    <div data-testid="preflight-banner" style={preflightBannerStyle}>
      {pf.route && (
        <span style={preflightRouteStyle}>
          {pf.route === 'free' ? 'Free route' : `Route: ${pf.route}`}
          {isPaid && (
            <span style={preflightCostStyle}>
              {' '}&middot; est. CAD {pf.estimated_cost_cad.toFixed(4)}
              <span style={preflightBasisStyle}> (local estimate)</span>
            </span>
          )}
        </span>
      )}
      {hasBlockingReasons && (
        <div style={preflightReasonsStyle}>
          {pf.reasons.map((reason, index) => (
            <div key={index} style={{ color: 'var(--color-warning)' }}>{reason}</div>
          ))}
        </div>
      )}
    </div>
  )
}

const preflightBannerStyle: CSSProperties = {
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)',
  background: 'var(--color-surface-elevated)',
  padding: '8px 10px',
  fontSize: 12,
  lineHeight: 1.5,
  display: 'grid',
  gap: 4,
}
const preflightRouteStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontWeight: 600,
  color: 'var(--color-text-secondary)',
}
const preflightCostStyle: CSSProperties = {
  fontWeight: 400,
}
const preflightBasisStyle: CSSProperties = {
  color: 'var(--color-text-muted)',
  fontSize: 11,
}
const preflightReasonsStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  lineHeight: 1.5,
}

const workCanvasStyle: CSSProperties = { width: '100%', maxWidth: 1120, margin: '0 auto', display: 'grid', gap: 20, alignContent: 'start' }
const workHeaderStyle: CSSProperties = { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }
const workHeaderActionsStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }
const secondaryActionStyle: CSSProperties = { minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px 12px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }
const degradedNoticeStyle: CSSProperties = { border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)', padding: '12px 14px', color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.5, display: 'grid', gap: 6 }
const sourceDetailsStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-muted)' }
const countStripStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap' }
const countStyle: CSSProperties = { border: '1px solid var(--color-separator)', borderRadius: 999, padding: '5px 10px', fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 600, background: 'var(--color-surface)' }
const summaryMetaStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--color-text-muted)' }
const groupHeaderStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }
const groupCountStyle: CSSProperties = { minWidth: 26, height: 26, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', borderRadius: 999, background: 'var(--color-surface-elevated)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 600 }
const groupListStyle: CSSProperties = { background: 'var(--color-surface)', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)', overflow: 'hidden' }
const showMoreStyle: CSSProperties = { minHeight: 44, justifySelf: 'start', padding: '8px 10px', borderRadius: 'var(--r-control)', background: 'transparent', color: 'var(--color-accent)', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }
const noticeStyle: CSSProperties = { border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', padding: '14px 16px', color: 'var(--color-text-secondary)' }
const sourceStatusStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 600 }
const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-muted)' }
const retryStyle: CSSProperties = { minHeight: 44, display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '8px 12px', background: 'var(--color-surface)', color: 'var(--color-text-primary)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600 }

const primaryActionStyle: CSSProperties = { minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px 14px', border: '1px solid var(--color-accent)', borderRadius: 'var(--r-control)', background: 'var(--color-accent)', color: 'var(--color-on-accent, #fff)', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }
const actionNoteStyle: CSSProperties = { color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 13, lineHeight: 1.5 }
const actionResultStyle: CSSProperties = { color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 12.5 }
const bannerStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)', padding: '12px 14px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 13.5, lineHeight: 1.5 }

const workRowStyle: CSSProperties = { padding: '14px 16px', display: 'grid', gap: 7 }
const stateLabelStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600 }
const evidenceRowStyle: CSSProperties = { display: 'flex', gap: '4px 12px', flexWrap: 'wrap', fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-muted)' }

const WORK_DETAIL_LABELS: Record<string, string> = {
  shadow_run_complete: 'The previous Builder run completed; this item remains blocked.',
  run_cancelled: 'The last Builder run was cancelled.',
  scope_violation: 'The last Builder run stopped after changing files outside its allowed scope.',
  stale_heartbeat: 'The last Builder run stopped reporting progress.',
  run_timeout: 'The last Builder run timed out.',
  worker_failed: 'The Builder worker failed.',
  recover: 'Recovery is available.',
  claim: 'Ready for Builder to claim.',
  exhausted: 'Automatic attempts are exhausted.',
  cancelled: 'Work was cancelled.',
  done: 'Work is complete.',
  await_review: 'Waiting for review.',
}

/**
 * What the user can actually do with a row, or why nothing is available.
 *
 * Every row resolves to one of these — a row that only describes its state is
 * a dead end, and the projection already computes `next_action` for exactly
 * this purpose. Kept pure so the mapping is testable without a gateway.
 */
export type RowAction =
  | { kind: 'command'; label: string; command: BuilderCommand; note?: string; confirm?: string }
  | { kind: 'tick'; label: string; note?: string; confirm: string }
  | { kind: 'none'; explanation: string }

export function rowAction(item: GatewayWorkItem, builderRunning: boolean): RowAction {
  const taskId = item.current_packet?.task_id ?? null
  const initiativeId = item.source.initiative_id

  if (item.state === 'paused') {
    return {
      kind: 'command',
      label: 'Resume this project',
      command: { action: 'resume', initiative_id: initiativeId },
      note: 'On hold. Nothing in it will run until you resume it.',
    }
  }

  switch (item.next_action) {
    case 'recover':
      if (!taskId) {
        return { kind: 'none', explanation: 'Kitty cannot retry this — Builder did not record which job it belongs to.' }
      }
      return {
        kind: 'command',
        label: 'Try again',
        command: { action: 'requeue', task_id: taskId, reason: 'Retried from Work' },
      }
    case 'exhausted': {
      const packetId = item.current_packet?.id ?? item.source.packet_id
      if (!packetId) {
        return { kind: 'none', explanation: 'Kitty cannot retry this — Builder did not record which packet used its retry budget.' }
      }
      return {
        kind: 'command',
        label: 'Try again',
        command: {
          action: 'grant_attempt',
          initiative_id: initiativeId,
          packet_id: packetId,
          reason: 'Granted one retry from Work',
        },
        note: 'Builder already used up its automatic retries on this one.',
      }
    }
    case 'claim':
      return builderRunning
        ? { kind: 'none', explanation: 'Ready to go. Builder will pick it up on its next pass.' }
        : { kind: 'tick', label: 'Start Builder', confirm: START_BUILDER_CONFIRM, note: 'Ready to go, but Builder is stopped.' }
    case 'await_review':
      return { kind: 'none', explanation: 'Finished and waiting for a review. Kitty cannot start that for you yet.' }
    case 'cancelled':
      return { kind: 'none', explanation: 'This was cancelled. Nothing to do.' }
    case 'done':
      return { kind: 'none', explanation: 'This one is finished.' }
    default:
      return { kind: 'none', explanation: 'No action is available for this yet.' }
  }
}

const START_BUILDER_CONFIRM =
  'Start Builder? It will begin working on jobs that are ready, which can use paid models.'

function canCancel(item: GatewayWorkItem): boolean {
  const terminal = item.next_action === 'cancelled' || item.next_action === 'done' || item.state === 'completed'
  return !terminal && Boolean(item.current_packet?.task_id)
}

function rawWorkDetail(item: GatewayWorkItem): string | null {
  return item.blocker?.reason || item.next_action || null
}

function workDetailLabel(item: GatewayWorkItem): string | null {
  const raw = rawWorkDetail(item)
  if (!raw) return null
  const known = Object.hasOwn(WORK_DETAIL_LABELS, raw) ? WORK_DETAIL_LABELS[raw] : undefined
  if (known) return known
  if (/^[a-z0-9]+(?:_[a-z0-9]+)+$/i.test(raw)) {
    const words = raw.replaceAll('_', ' ')
    return `${words.charAt(0).toUpperCase()}${words.slice(1)}.`
  }
  return raw
}

function WorkRow({ item, isLast, builderRunning }: { item: GatewayWorkItem; isLast: boolean; builderRunning: boolean }) {
  const approval = approvalLabel(item)
  const rawDetail = rawWorkDetail(item)
  const detail = workDetailLabel(item)
  const evidence = evidenceLabels(item)
  return (
    <article
      data-testid="work-row"
      style={{ ...workRowStyle, borderBottom: isLast ? 'none' : '1px solid var(--color-separator)' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: STATE_COLORS[item.state], flexShrink: 0 }} />
        <strong style={{ color: 'var(--color-text-primary)', fontSize: 14.5, lineHeight: 1.35 }}>{item.title || item.id}</strong>
        <span style={{ ...stateLabelStyle, color: STATE_COLORS[item.state] }}>{item.state}</span>
      </div>
      {detail && <div style={{ color: 'var(--color-text-secondary)', fontSize: 13.5, lineHeight: 1.5 }}>{detail}</div>}
      <RowActions item={item} builderRunning={builderRunning} />
      {evidence.length > 0 && (
        <div style={evidenceRowStyle}>
          {evidence.map(label => <span key={label}>{label}</span>)}
        </div>
      )}
      <details style={metaStyle}>
        <summary style={{ cursor: 'pointer', color: 'var(--color-text-secondary)', minHeight: 32, display: 'flex', alignItems: 'center' }}>Details</summary>
        <div style={{ display: 'grid', gap: 4, marginTop: 6 }}>
          <div>initiative <span>{item.id}</span></div>
          {item.current_packet?.id && <div>packet <span>{item.current_packet.id}</span></div>}
          {item.current_packet?.task_id && <div>task <span>{item.current_packet.task_id}</span></div>}
          {item.current_run?.id && <div>run <span>{item.current_run.id}</span></div>}
          {item.current_packet?.task_state && <div>task state {item.current_packet.task_state}</div>}
          {rawDetail && <div>raw reason <span>{rawDetail}</span></div>}
          {approval && <div>{approval}</div>}
          <EvidenceDetails evidence={item.evidence} />
          {item.data_quality.issues?.map(issue => <div key={issue}>quality: {issue}</div>)}
        </div>
      </details>
    </article>
  )
}


function RowActions({ item, builderRunning }: { item: GatewayWorkItem; builderRunning: boolean }) {
  const action = rowAction(item, builderRunning)
  const builderAction = useBuilderAction()
  const [result, setResult] = useState<string | null>(null)

  const run = (command: BuilderCommand | 'tick', confirmText?: string) => {
    if (confirmText && !globalThis.confirm(confirmText)) return
    setResult(null)
    builderAction.mutate(command, {
      onSuccess: outcome => setResult(outcome.ok ? 'Done. Refreshing…' : (outcome.error ?? 'Builder refused that.')),
      onError: error => setResult(error instanceof Error ? error.message : 'That did not go through.'),
    })
  }

  const note = action.kind === 'none' ? action.explanation : action.note
  const busy = builderAction.isPending

  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {note && (
        <div data-testid={action.kind === 'none' ? 'row-no-action' : 'row-action-note'} style={actionNoteStyle}>
          {note}
        </div>
      )}
      {action.kind !== 'none' && (
        <div data-testid="row-action" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            disabled={busy}
            onClick={() => run(action.kind === 'tick' ? 'tick' : action.command, action.confirm)}
            style={{ ...primaryActionStyle, opacity: busy ? 0.6 : 1 }}
          >
            {busy ? 'Working…' : action.label}
          </button>
          {canCancel(item) && (
            <button
              type="button"
              disabled={busy}
              onClick={() => run(
                { action: 'cancel', task_id: item.current_packet!.task_id!, reason: 'Cancelled from Work' },
                `Cancel "${item.title || item.id}"? It will stop and stay stopped until you send it back.`,
              )}
              style={{ ...secondaryActionStyle, opacity: busy ? 0.6 : 1 }}
            >
              Cancel it
            </button>
          )}
        </div>
      )}
      <PreflightBanner item={item} />
      {result && <div role="status" style={actionResultStyle}>{result}</div>}
    </div>
  )
}

function BuilderRunBanner({ supervisor }: { supervisor: GatewaySupervisor }) {
  const builderAction = useBuilderAction()
  const [result, setResult] = useState<string | null>(null)

  if (supervisor.running) {
    return (
      <div style={bannerStyle}>
        <div style={{ display: 'grid', gap: 4 }}>
          <div><strong>Builder is working.</strong> {describeReady(supervisor)}</div>
          <span>{describeBudget(supervisor)}</span>
        </div>
      </div>
    )
  }

  const start = () => {
    if (!globalThis.confirm(START_BUILDER_CONFIRM)) return
    setResult(null)
    builderAction.mutate('tick', {
      onSuccess: outcome => setResult(outcome.ok ? 'Builder started.' : (outcome.error ?? 'Builder could not start.')),
      onError: error => setResult(error instanceof Error ? error.message : 'Builder could not start.'),
    })
  }

  return (
    <div style={bannerStyle}>
      <div style={{ display: 'grid', gap: 4 }}>
        <strong>Builder is stopped.</strong>
        <span>Nothing moves until you start it. {describeReady(supervisor)}</span>
        <span>{describeBudget(supervisor)}</span>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          type="button"
          disabled={builderAction.isPending || supervisor.eligible_now === 0}
          onClick={start}
          style={{ ...primaryActionStyle, opacity: builderAction.isPending || supervisor.eligible_now === 0 ? 0.6 : 1 }}
        >
          {builderAction.isPending ? 'Starting…' : 'Start Builder'}
        </button>
        {result && <span role="status" style={actionResultStyle}>{result}</span>}
      </div>
    </div>
  )
}

function describeBudget(supervisor: GatewaySupervisor): string {
  const spent = supervisor.budget.estimated_spend_cad.toFixed(2)
  const budget = supervisor.budget.weekly_budget_cad.toFixed(2)
  const runWord = supervisor.budget.runs === 1 ? 'run' : 'runs'
  return `CAD ${spent} of CAD ${budget} estimated this week · ${supervisor.budget.runs} ${runWord}.`
}

function describeReady(supervisor: GatewaySupervisor): string {
  const ready = supervisor.eligible_now === 1 ? '1 job is ready to run' : `${supervisor.eligible_now} jobs are ready to run`
  if (supervisor.on_hold === 0) return `${ready}.`
  const held = supervisor.on_hold === 1 ? '1 more is' : `${supervisor.on_hold} more are`
  return `${ready}. ${held} on hold until their project is resumed.`
}

function evidenceRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function evidenceScalar(value: unknown): string | null {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return null
}

function boundedEvidenceText(value: unknown): string | null {
  const text = evidenceScalar(value)?.trim()
  if (!text) return null
  return text.length <= 240 ? text : `${text.slice(0, 239).trimEnd()}…`
}

function evidenceDate(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = /(?:Z|[+-]\\d{2}:?\\d{2})$/i.test(value) ? value : `${value.replace(' ', 'T')}Z`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

function EvidenceDetails({ evidence }: { evidence: Record<string, unknown> }) {
  const review = evidenceRecord(evidence.review)
  const validation = evidenceRecord(evidence.validation)
  const publication = evidenceRecord(evidence.publication)
  const reviewVerdict = evidenceScalar(review?.verdict)
  const reviewSummary = boundedEvidenceText(review?.summary)
  const validationStatus = evidenceScalar(validation?.status)
  const validationSummary = boundedEvidenceText(validation?.summary)
  const publicationPr = evidenceScalar(publication?.pr_number)
  const publicationChecks = evidenceScalar(publication?.checks_state)
  const publicationMerged = typeof publication?.merged === 'boolean' ? publication.merged : null
  const publicationMergedAt = evidenceDate(publication?.merged_at)

  return (
    <>
      {review && <div>review {reviewVerdict ?? 'recorded'}</div>}
      {reviewSummary && <div>{reviewSummary}</div>}
      {validation && <div>validation {validationStatus ?? 'recorded'}</div>}
      {validationSummary && <div>{validationSummary}</div>}
      {publicationPr && <div>publication PR #{publicationPr}</div>}
      {publicationChecks && <div>publication checks {publicationChecks}</div>}
      {publicationMerged !== null && <div>publication {publicationMerged ? 'merged' : 'not merged'}</div>}
      {publicationMerged === true && publicationMergedAt && <div>merged {publicationMergedAt}</div>}
    </>
  )
}

function evidenceLabels(item: GatewayWorkItem): string[] {
  const labels: string[] = []
  if (item.evidence.review) labels.push('Review evidence available')
  if (item.evidence.publication) labels.push('Publication evidence available')
  if (item.evidence.validation) labels.push('Validation evidence available')
  return labels
}
