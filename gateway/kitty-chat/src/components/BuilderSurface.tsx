'use client'

import { useState, type CSSProperties } from 'react'

import { bodyText, card, cardHeader, cardMeta, cardTitle, emptyState, itemCard } from '@/lib/ui'
import { useGatewayRuntimeManifest } from '@/lib/queries'
import type {
  BuilderAttemptStatus,
  BuilderPacketStatus,
  BuilderStatusSnapshot,
  RuntimeFact,
} from '@/lib/gateway'

interface BuilderSurfaceProps {
  fact?: RuntimeFact<BuilderStatusSnapshot>
  isLoading: boolean
  error?: string | null
  onBack?: () => void
}

interface BuilderGlanceProps {
  onOpen: () => void
}

const actionButton: CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: 4,
  background: 'var(--surface)',
  color: 'var(--ink)',
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 600,
  padding: '7px 10px',
}

const detailGrid: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 190px), 1fr))',
  gap: 10,
}

/**
 * Query-backed home glance. The full surface stays renderable without a live
 * gateway so its facts, loading state, and failure state remain testable.
 */
export function BuilderGlance({ onOpen }: BuilderGlanceProps) {
  const query = useGatewayRuntimeManifest()
  const fact = query.data?.execution.builder
  const snapshot = fact?.value
  const attention = snapshot ? attentionCount(snapshot) : 0
  const active = snapshot ? activePacketCount(snapshot) : 0

  return (
    <section style={{ ...card, display: 'grid', gap: 12 }} aria-label="Builder status glance">
      <div style={cardHeader}>
        <div style={cardTitle}>builder</div>
        <span style={cardMeta}>{builderGlanceLabel(fact, query.isLoading, attention, active)}</span>
      </div>
      <p style={{ ...bodyText, margin: 0 }}>
        {builderGlanceDetail(fact, query.isLoading, query.error)}
      </p>
      <div>
        <button type="button" onClick={onOpen} style={actionButton}>
          Open Builder
        </button>
      </div>
    </section>
  )
}

/** A read-only, bounded view of Builder's durable runtime projection. */
export function BuilderPanel({ onBack }: { onBack?: () => void }) {
  const query = useGatewayRuntimeManifest()
  return (
    <BuilderSurface
      fact={query.data?.execution.builder}
      isLoading={query.isLoading}
      error={query.error instanceof Error ? query.error.message : null}
      onBack={onBack}
    />
  )
}

export function BuilderSurface({ fact, isLoading, error, onBack }: BuilderSurfaceProps) {
  const [selectedPacketId, setSelectedPacketId] = useState<string | null>(null)
  const snapshot = fact?.value
  const stale = fact?.state === 'stale' || isExpired(fact?.valid_until)
  const selectedPacket = selectedPacketId ? findPacket(snapshot, selectedPacketId) : null

  if (isLoading && !fact) {
    return <LoadingState onBack={onBack} />
  }

  if (!snapshot || fact?.state === 'unavailable' || fact?.state === 'unknown') {
    return <UnavailableState fact={fact} error={error} onBack={onBack} />
  }

  if (selectedPacket) {
    return (
      <PacketDetail
        packet={selectedPacket}
        stale={stale}
        onBack={() => setSelectedPacketId(null)}
        onHome={onBack}
      />
    )
  }

  return (
    <section style={{ display: 'grid', gap: 16, maxWidth: 1120, width: '100%' }}>
      <SurfaceHeader onBack={onBack} />
      {stale && <StaleNotice />}
      {snapshot.initiatives.length === 0 ? (
        <div style={card}>
          <p style={{ ...emptyState, margin: 0 }}>No Builder work is recorded yet.</p>
        </div>
      ) : (
        <BuilderOverview snapshot={snapshot} onSelectPacket={setSelectedPacketId} />
      )}
    </section>
  )
}

function LoadingState({ onBack }: { onBack?: () => void }) {
  return (
    <section style={{ display: 'grid', gap: 16, maxWidth: 1120, width: '100%' }}>
      <SurfaceHeader onBack={onBack} />
      <div style={{ ...card, display: 'grid', gap: 10 }} aria-label="Loading Builder status">
        <div style={{ height: 12, width: '32%', background: 'var(--surface-2)', borderRadius: 3 }} />
        <div style={{ height: 68, background: 'var(--surface-2)', borderRadius: 3 }} />
      </div>
    </section>
  )
}

function UnavailableState({
  fact,
  error,
  onBack,
}: {
  fact?: RuntimeFact<BuilderStatusSnapshot>
  error?: string | null
  onBack?: () => void
}) {
  const detail = fact?.reason || error || 'The runtime manifest did not return Builder state.'
  return (
    <section style={{ display: 'grid', gap: 16, maxWidth: 1120, width: '100%' }}>
      <SurfaceHeader onBack={onBack} />
      <div style={{ ...card, display: 'grid', gap: 8 }} role="status">
        <strong style={{ fontFamily: 'var(--font-body)', color: 'var(--ink)' }}>Builder unavailable</strong>
        <p style={{ ...bodyText, margin: 0, overflowWrap: 'anywhere' }}>{detail}</p>
      </div>
    </section>
  )
}

function SurfaceHeader({ onBack }: { onBack?: () => void }) {
  return (
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <div>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Builder</h1>
        <p style={{ ...bodyText, margin: '4px 0 0' }}>Read-only execution status from durable Builder records.</p>
      </div>
      {onBack && (
        <button type="button" onClick={onBack} style={actionButton}>
          Back to home
        </button>
      )}
    </header>
  )
}

function StaleNotice() {
  return (
    <p role="status" style={{ ...bodyText, margin: 0, color: 'var(--warning, var(--ink-2))' }}>
      Data may be stale. The last Builder snapshot is shown while the next manifest refresh is pending.
    </p>
  )
}

function BuilderOverview({
  snapshot,
  onSelectPacket,
}: {
  snapshot: BuilderStatusSnapshot
  onSelectPacket: (packetId: string) => void
}) {
  const attention = attentionCount(snapshot)
  const active = activePacketCount(snapshot)
  return (
    <>
      <div style={detailGrid}>
        <Metric label="needs attention" value={attention} />
        <Metric label="active work" value={active} />
        <Metric label="queued work" value={snapshot.queue.queued} />
        <Metric label="completed" value={snapshot.queue.done} />
      </div>
      {snapshot.initiatives.map((initiative) => (
        <section key={initiative.initiative_id} style={{ ...card, display: 'grid', gap: 12 }}>
          <div style={cardHeader}>
            <div>
              <div style={cardTitle}>{initiative.title}</div>
              <div style={{ ...cardMeta, marginTop: 4 }}>{displayState(initiative.state)}</div>
            </div>
            <span style={cardMeta}>{initiative.counts.total} packets</span>
          </div>
          {initiative.pause_reason && <p style={{ ...bodyText, margin: 0 }}>{initiative.pause_reason}</p>}
          <div style={{ display: 'grid', gap: 8 }}>
            {initiative.packets.map((packet) => (
              <button
                key={packet.packet_id}
                type="button"
                onClick={() => onSelectPacket(packet.packet_id)}
                aria-label={`View packet ${packet.title}`}
                style={{
                  ...itemCard,
                  cursor: 'pointer',
                  textAlign: 'left',
                  color: 'var(--ink)',
                  display: 'grid',
                  gap: 5,
                  overflowWrap: 'anywhere',
                }}
              >
                <span style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600 }}>{packet.title}</span>
                <span style={cardMeta}>
                  {packet.packet_id} · {packetSummary(packet)}
                </span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </>
  )
}

function PacketDetail({
  packet,
  stale,
  onBack,
  onHome,
}: {
  packet: BuilderPacketStatus
  stale: boolean
  onBack: () => void
  onHome?: () => void
}) {
  return (
    <section style={{ display: 'grid', gap: 16, maxWidth: 1120, width: '100%' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ ...cardMeta, margin: 0 }}>{packet.packet_id}</p>
          <h2 style={{ margin: '4px 0 0', fontFamily: 'var(--font-display)', fontSize: 28, color: 'var(--ink)', overflowWrap: 'anywhere' }}>
            {packet.title}
          </h2>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={onBack} style={actionButton}>Back to overview</button>
          {onHome && <button type="button" onClick={onHome} style={actionButton}>Back to home</button>}
        </div>
      </header>
      {stale && <StaleNotice />}
      <div style={detailGrid}>
        <Metric label="task state" value={displayState(packet.task_state ?? 'unavailable')} />
        <Metric label="attempt budget" value={`${packet.budget.used}/${packet.budget.max}`} />
        <Metric label="eligibility" value={displayState(packet.eligibility.state)} />
        <Metric label="base" value={packet.base_sha ? packet.base_sha.slice(0, 12) : 'unavailable'} />
      </div>
      <div style={{ ...card, display: 'grid', gap: 14 }}>
        <div style={cardHeader}><span style={cardTitle}>Current status</span></div>
        <StatusDetail label="Failure classification" value={failureLabel(packet.failure_kind)} />
        <StatusDetail label="Blocked reason" value={packet.blocked_reason} />
        <StatusDetail label="Last error" value={packet.last_error} />
        {packet.eligibility.blocked_by.length > 0 && (
          <StatusDetail label="Blocked by" value={packet.eligibility.blocked_by.join(', ')} />
        )}
        <StatusDetail label="Latest durable event" value={eventSummary(packet)} />
      </div>
      <div style={{ ...card, display: 'grid', gap: 12 }}>
        <div style={cardHeader}><h3 style={{ ...cardTitle, margin: 0 }}>Attempt history</h3></div>
        {packet.attempt || packet.previous_attempt ? (
          <div style={{ display: 'grid', gap: 8 }}>
            {packet.attempt && <AttemptCard label="Current attempt" attempt={packet.attempt} />}
            {packet.previous_attempt && <AttemptCard label="Previous attempt" attempt={packet.previous_attempt} />}
          </div>
        ) : <p style={{ ...emptyState, margin: 0 }}>No attempts have been recorded.</p>}
      </div>
      <div style={detailGrid}>
        <RunCard packet={packet} />
        <PublicationCard packet={packet} />
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ ...card, display: 'grid', gap: 4, minWidth: 0 }}>
      <span style={cardMeta}>{label}</span>
      <strong style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--ink)', overflowWrap: 'anywhere' }}>
        {typeof value === 'number' && label === 'needs attention' ? `${value} needs attention` : value}
      </strong>
    </div>
  )
}

function StatusDetail({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div style={{ display: 'grid', gap: 3 }}>
      <span style={cardMeta}>{label}</span>
      <span style={{ ...bodyText, color: 'var(--ink)', overflowWrap: 'anywhere' }}>{value}</span>
    </div>
  )
}

function AttemptCard({ label, attempt }: { label: string; attempt: BuilderAttemptStatus }) {
  return (
    <div style={{ ...itemCard, display: 'grid', gap: 4 }}>
      <strong style={{ fontFamily: 'var(--font-body)', fontSize: 13 }}>{label} · #{attempt.number}</strong>
      <span style={cardMeta}>{attempt.outcome ? displayState(attempt.outcome) : 'in progress'}</span>
      {attempt.implementation_status && <span style={bodyText}>Implementation {displayState(attempt.implementation_status)}</span>}
      {attempt.validation_status && <span style={bodyText}>Validation {displayState(attempt.validation_status)}</span>}
      {attempt.review_verdict && <span style={bodyText}>{reviewLabel(attempt.review_verdict)}</span>}
    </div>
  )
}

function RunCard({ packet }: { packet: BuilderPacketStatus }) {
  return (
    <div style={{ ...card, display: 'grid', gap: 6 }}>
      <span style={cardTitle}>Latest run</span>
      {packet.run ? (
        <>
          <span style={bodyText}>{displayState(packet.run.state)}</span>
          {packet.run.exit_code !== null && <span style={cardMeta}>Exit code {packet.run.exit_code}</span>}
        </>
      ) : <span style={bodyText}>No run recorded.</span>}
    </div>
  )
}

function PublicationCard({ packet }: { packet: BuilderPacketStatus }) {
  const publication = packet.publication
  return (
    <div style={{ ...card, display: 'grid', gap: 6 }}>
      <span style={cardTitle}>Publication</span>
      {publication ? (
        <>
          <span style={bodyText}>{publication.merged ? 'Merged' : displayState(publication.checks_state ?? 'recorded')}</span>
          {publication.pr_url && (
            <a href={publication.pr_url} target="_blank" rel="noreferrer" style={{ ...bodyText, color: 'var(--primary)', overflowWrap: 'anywhere' }}>
              Open pull request
            </a>
          )}
        </>
      ) : <span style={bodyText}>No pull request recorded.</span>}
    </div>
  )
}

function attentionCount(snapshot: BuilderStatusSnapshot): number {
  return snapshot.initiatives.flatMap((initiative) => initiative.packets).filter((packet) => (
    packet.task_state === 'blocked'
    || packet.task_state === 'failed'
    || packet.task_state === 'cancelled'
    || packet.budget.exhausted
    || packet.failure_kind !== null
  )).length
}

function activePacketCount(snapshot: BuilderStatusSnapshot): number {
  return snapshot.initiatives.flatMap((initiative) => initiative.packets).filter((packet) => (
    packet.run?.state === 'starting'
    || packet.run?.state === 'running'
    || packet.run?.state === 'cancel_requested'
  )).length
}

function findPacket(
  snapshot: BuilderStatusSnapshot | null | undefined,
  packetId: string,
): BuilderPacketStatus | null {
  if (!snapshot) return null
  for (const initiative of snapshot.initiatives) {
    const packet = initiative.packets.find((candidate) => candidate.packet_id === packetId)
    if (packet) return packet
  }
  return null
}

function builderGlanceLabel(
  fact: RuntimeFact<BuilderStatusSnapshot> | undefined,
  isLoading: boolean,
  attention: number,
  active: number,
): string {
  if (isLoading && !fact) return 'loading'
  if (!fact?.value || fact.state === 'unavailable' || fact.state === 'unknown') return 'unavailable'
  if (attention) return `${attention} needs attention`
  if (active) return `${active} active`
  if (fact.value.queue.total === 0) return 'no work yet'
  return 'up to date'
}

function builderGlanceDetail(
  fact: RuntimeFact<BuilderStatusSnapshot> | undefined,
  isLoading: boolean,
  error: unknown,
): string {
  if (isLoading && !fact) return 'Checking the Builder runtime manifest.'
  if (!fact?.value || fact.state === 'unavailable' || fact.state === 'unknown') {
    return fact?.reason || (error instanceof Error ? error.message : 'Builder state is not available from the runtime manifest.')
  }
  const snapshot = fact.value
  const active = activePacketCount(snapshot)
  if (active) return `${active} packet${active === 1 ? '' : 's'} active. This surface refreshes more often while work is running.`
  if (snapshot.queue.total === 0) return 'No Builder work is recorded yet.'
  return `${snapshot.queue.done} complete, ${snapshot.queue.queued} queued, ${snapshot.queue.blocked} blocked.`
}

function packetSummary(packet: BuilderPacketStatus): string {
  return failureLabel(packet.failure_kind) || displayState(packet.task_state ?? packet.eligibility.state)
}

function eventSummary(packet: BuilderPacketStatus): string | null {
  if (!packet.last_event) return null
  const label = displayState(packet.last_event.type)
  return packet.last_event.reason ? `${label}: ${packet.last_event.reason}` : label
}

function failureLabel(kind: BuilderPacketStatus['failure_kind']): string | null {
  const labels: Record<NonNullable<BuilderPacketStatus['failure_kind']>, string> = {
    implementation: 'Implementation failure',
    identity: 'Identity failure',
    validation: 'Validation failure',
    review: 'Review failure',
    infrastructure: 'Infrastructure failure',
    cancelled: 'Cancelled',
    exhausted: 'Attempt budget exhausted',
  }
  return kind ? labels[kind] : null
}

function reviewLabel(verdict: NonNullable<BuilderAttemptStatus['review_verdict']>): string {
  if (verdict === 'reject') return 'Review rejected'
  if (verdict === 'request_changes') return 'Review changes requested'
  return 'Review approved'
}

function displayState(value: string): string {
  return value.replace(/_/g, ' ')
}

function isExpired(validUntil: string | undefined): boolean {
  if (!validUntil) return false
  const timestamp = Date.parse(validUntil)
  return Number.isFinite(timestamp) && timestamp < Date.now()
}
