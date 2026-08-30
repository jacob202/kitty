'use client'

import { useState, type CSSProperties, type ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import { usePreflight, useSupervisor, useWorkSnapshot, type GatewayWorkItem, type GatewayWorkState } from '@/lib/work'
import { approveBuilderJob, proposeBuilderJob, type ConversationProposal } from '@/lib/gateway'

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
          <SchedulerStatus supervisor={supervisor.data} failed={supervisor.isError} />
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
            <BuilderCockpit onSent={() => void work.refetch()} />
            <div style={countStripStyle} aria-label="Work status summary">
              {(['active', 'blocked', 'failed', 'ready', 'waiting', 'paused', 'completed'] as GatewayWorkState[])
                .filter(state => snapshot.counts[state] > 0)
                .map(state => <Count key={state} state={state} value={snapshot.counts[state]} />)}
            </div>
            {snapshot.total_items > snapshot.items.length && (
              <div style={summaryMetaStyle}>Showing {snapshot.items.length} of {snapshot.total_items} most relevant items from Builder.</div>
            )}
            {snapshot.items.length === 0 ? <Notice>No Builder work is currently projected.</Notice> : (
              <div style={{ display: 'grid', gap: 22 }}>
                {(['needs-you', 'in-progress', 'completed'] as WorkGroup[]).map(group => {
                  const items = snapshot.items.filter(item => workGroup(item) === group)
                  if (items.length === 0) return null
                  return <WorkGroupSection key={group} group={group} items={items} />
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function WorkGroupSection({ group, items }: { group: WorkGroup; items: GatewayWorkItem[] }) {
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
          <WorkRow key={item.id} item={item} isLast={index === visibleItems.length - 1} />
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

function SchedulerStatus({ supervisor, failed }: { supervisor: ReturnType<typeof useSupervisor>['data']; failed: boolean }) {
  if (failed) return <div style={degradedNoticeStyle}>Scheduled Builder status is unavailable.</div>
  if (!supervisor) return null
  const scheduler = supervisor.scheduler
  const state = scheduler.healthy ? 'healthy' : scheduler.installed ? 'needs attention' : 'not installed'
  return (
    <div data-testid="builder-scheduler-status" style={preflightBannerStyle}>
      <strong>Scheduled Builder: {state}</strong>
      {scheduler.start_interval_seconds && <span>every {Math.round(scheduler.start_interval_seconds / 60)} min</span>}
      <span>{scheduler.loaded ? 'loaded' : 'not loaded'}</span>
      {scheduler.last_exit_status !== null && <span>last exit {scheduler.last_exit_status}</span>}
      {scheduler.reason && <span>{scheduler.reason}</span>}
      {scheduler.last_tick_at === null && <span>last tick time unavailable</span>}
      {scheduler.next_run_at === null && <span>next run time unavailable</span>}
    </div>
  )
}

function BuilderCockpit({ onSent }: { onSent: () => void }) {
  const [objective, setObjective] = useState('')
  const [paths, setPaths] = useState('')
  const [proposal, setProposal] = useState<ConversationProposal | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const allowedPaths = paths.split(/[\n,]+/).map(path => path.trim()).filter(Boolean)
  const canPrepare = objective.trim().length >= 8 && allowedPaths.length > 0 && !busy
  const canSend = Boolean(
    proposal?.prepared_manifest && proposal.manifest_sha256 && proposal.expected_base_sha && proposal.approval_nonce,
  ) && !busy

  async function prepare() {
    if (!canPrepare) return
    setBusy(true); setMessage(null); setProposal(null)
    try {
      const next = await proposeBuilderJob({
        objective: objective.trim(),
        instructions: objective.trim(),
        allowed_paths: allowedPaths,
        title: objective.trim().slice(0, 96),
        acceptance_criteria: [`Complete the requested work within: ${allowedPaths.join(', ')}`],
      })
      if (!next.ok) throw new Error(next.error || 'Builder could not prepare the proposal.')
      setProposal(next)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Builder could not prepare the proposal.')
    } finally { setBusy(false) }
  }

  async function send() {
    if (!proposal?.prepared_manifest || !proposal.manifest_sha256 || !proposal.expected_base_sha || !proposal.approval_nonce) return
    setBusy(true); setMessage(null)
    try {
      const result = await approveBuilderJob({
        prepared_manifest: proposal.prepared_manifest,
        expected_manifest_sha: proposal.manifest_sha256,
        expected_base_sha: proposal.expected_base_sha,
        approval_nonce: proposal.approval_nonce,
        confirmed: true,
      })
      if (!result.ok) throw new Error(result.error || 'Builder could not queue the proposal.')
      setMessage('Sent to Builder. It will appear in Work as durable status updates arrive.')
      setProposal(null); setObjective(''); setPaths(''); onSent()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Builder could not queue the proposal.')
    } finally { setBusy(false) }
  }

  return (
    <section aria-label="Ask Builder" style={cockpitStyle}>
      <div style={{ display: 'grid', gap: 4 }}>
        <strong style={{ color: 'var(--color-text-primary)' }}>Ask Builder</strong>
        <span style={summaryMetaStyle}>Prepare bounded work here, review it, then explicitly send it.</span>
      </div>
      <textarea aria-label="What should Builder do?" value={objective} onChange={event => setObjective(event.target.value)} placeholder="What should Builder do?" rows={3} style={cockpitInputStyle} />
      <input aria-label="Allowed paths" value={paths} onChange={event => setPaths(event.target.value)} placeholder="Allowed paths, comma separated — e.g. gateway/kitty-chat/src, tests" style={cockpitInputStyle} />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" onClick={() => void prepare()} disabled={!canPrepare} style={secondaryActionStyle}>Prepare proposal</button>
        {proposal && <button type="button" onClick={() => void send()} disabled={!canSend} style={secondaryActionStyle}>Send to Builder</button>}
      </div>
      {proposal && (
        <div data-testid="builder-proposal-preview" style={preflightBannerStyle}>
          <strong>Proposal ready.</strong>
          <span>{objective.trim()}</span>
          <span>scope: {allowedPaths.join(', ')}</span>
          {proposal.warnings?.map(warning => <span key={warning}>{warning}</span>)}
        </div>
      )}
      {message && <div role="status" style={preflightBannerStyle}>{message}</div>}
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

const cockpitStyle: CSSProperties = { display: 'grid', gap: 10, border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)', background: 'var(--color-surface)', padding: '14px 16px' }
const cockpitInputStyle: CSSProperties = { width: '100%', boxSizing: 'border-box', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)', color: 'var(--color-text-primary)', padding: '10px 12px', fontFamily: 'var(--font-body)', fontSize: 13 }
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

const workRowStyle: CSSProperties = { padding: '14px 16px', display: 'grid', gap: 7 }
const stateLabelStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600 }
const evidenceRowStyle: CSSProperties = { display: 'flex', gap: '4px 12px', flexWrap: 'wrap', fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-muted)' }
const preflightBannerStyle: CSSProperties = { display: 'flex', gap: '4px 10px', flexWrap: 'wrap', alignItems: 'center', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '8px 10px', fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-secondary)', background: 'var(--color-surface-elevated)' }
const preflightErrorStyle: CSSProperties = { ...preflightBannerStyle, color: 'var(--color-warning)' }

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

function WorkRow({ item, isLast }: { item: GatewayWorkItem; isLast: boolean }) {
  const approval = approvalLabel(item)
  const rawDetail = rawWorkDetail(item)
  const detail = workDetailLabel(item)
  const evidence = evidenceLabels(item)
  const packetId = item.current_packet?.id ?? item.source.packet_id
  const preflight = usePreflight(
    item.next_action === 'claim' ? item.source.initiative_id : null,
    item.next_action === 'claim' ? packetId : null,
  )
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
      {preflight.data && (
        <div data-testid="preflight-banner" style={preflightBannerStyle}>
          <strong>Preflight {preflight.data.action === 'run' ? 'ready' : preflight.data.action}</strong>
          {preflight.data.route && <span>{preflight.data.route}</span>}
          <span>CAD {preflight.data.estimated_cost_cad.toFixed(4)} local estimate</span>
          {preflight.data.reasons.length > 0 && <span>{preflight.data.reasons[0]}</span>}
        </div>
      )}
      {preflight.isError && item.next_action === 'claim' && (
        <div style={preflightErrorStyle}>Preflight is unavailable; Builder should not start this packet until the check succeeds.</div>
      )}
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
