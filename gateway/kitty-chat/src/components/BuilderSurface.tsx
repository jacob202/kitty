'use client'

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import { bodyText, card, cardHeader, cardMeta, cardTitle, emptyState, itemCard } from '@/lib/ui'
import { useGatewayRuntimeManifest, useBuilderAction } from '@/lib/queries'
import { Button } from '@/components/ui/Button'
import { ArrowLeft, Home } from 'lucide-react'
import type {
  BuilderAttemptStatus,
  BuilderFailureKind,
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

interface PacketSelection {
  initiativeId: string
  packetId: string
}

interface BuilderNextAction {
  label: string
  detail: string
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
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 210px), 1fr))',
  gap: 10,
  minWidth: 0,
}

const surfaceLayout: CSSProperties = {
  display: 'grid',
  gap: 16,
  maxWidth: 1120,
  minWidth: 0,
  width: '100%',
  boxSizing: 'border-box',
}

/** Home-page summary backed by the same truthful runtime fact as the detail view. */
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
        <span style={cardMeta}>
          {builderGlanceLabel(fact, query.isLoading, attention, active)}
        </span>
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
  const [selection, setSelection] = useState<PacketSelection | null>(null)
  const [allPacketsOpen, setAllPacketsOpen] = useState(false)
  const packetButtonRefs = useRef(new Map<string, HTMLButtonElement>())
  const allPacketsButtonRef = useRef<HTMLButtonElement>(null)
  const snapshot = fact?.value
  const stale = fact?.state === 'stale' || isExpired(fact?.valid_until)
  const selectedPacket = selection ? findPacket(snapshot, selection) : null

  const returnToOverview = () => {
    const selectedKey = selection ? packetSelectionKey(selection) : null
    setSelection(null)
    if (selectedKey) {
      requestAnimationFrame(() => packetButtonRefs.current.get(selectedKey)?.focus())
    }
  }

  const registerPacketButton = (
    packetSelection: PacketSelection,
    node: HTMLButtonElement | null,
  ) => {
    const key = packetSelectionKey(packetSelection)
    if (node) {
      packetButtonRefs.current.set(key, node)
    } else {
      packetButtonRefs.current.delete(key)
    }
  }

  const closeAllPackets = () => {
    setAllPacketsOpen(false)
    requestAnimationFrame(() => allPacketsButtonRef.current?.focus())
  }

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
        degradedReason={fact.state === 'degraded' ? fact.reason : null}
        onBack={returnToOverview}
        onHome={onBack}
      />
    )
  }

  return (
    <section style={surfaceLayout}>
      <SurfaceHeader onBack={onBack} observedAt={fact.observed_at} />
      {stale && <StaleNotice />}
      {fact.state === 'degraded' && fact.reason && (
        <DataQualityNotice detail={fact.reason} />
      )}
      {snapshot.initiatives.length === 0 ? (
        <div style={card}>
          <p style={{ ...emptyState, margin: 0 }}>No Builder work is recorded yet.</p>
        </div>
      ) : (
        <>
          <BuilderNextActionCard
            snapshot={snapshot}
            onOpenAllPackets={() => setAllPacketsOpen(true)}
            allPacketsButtonRef={allPacketsButtonRef}
          />
          <BuilderInitiativeCards snapshot={snapshot} />
          <BuilderControls
            snapshot={snapshot}
            selection={selection}
            onRefresh={() => document.location.reload()}
          />
          <BuilderOverview
            snapshot={snapshot}
            onSelectPacket={setSelection}
            registerPacketButton={registerPacketButton}
          />
          {allPacketsOpen && (
            <AllPacketsModal
              snapshot={snapshot}
              onClose={closeAllPackets}
              onSelectPacket={(packet) => {
                setAllPacketsOpen(false)
                setSelection(packet)
              }}
            />
          )}
        </>
      )}
    </section>
  )
}

function LoadingState({ onBack }: { onBack?: () => void }) {
  return (
    <section style={surfaceLayout}>
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
    <section style={surfaceLayout}>
      <SurfaceHeader onBack={onBack} observedAt={fact?.observed_at} />
      <div style={{ ...card, display: 'grid', gap: 8 }} role="status">
        <strong style={{ fontFamily: 'var(--font-body)', color: 'var(--ink)' }}>
          Builder unavailable
        </strong>
        <p style={{ ...bodyText, margin: 0, overflowWrap: 'anywhere' }}>{detail}</p>
      </div>
    </section>
  )
}

function SurfaceHeader({ onBack, observedAt }: { onBack?: () => void; observedAt?: string }) {
  return (
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <div style={{ minWidth: 0 }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>
          Builder
        </h1>
        <p style={{ ...bodyText, margin: '4px 0 0' }}>
          Read-only execution status from durable Builder records.
        </p>
        {observedAt && (
          <p style={{ ...cardMeta, margin: '4px 0 0' }}>
            Snapshot observed <TimeValue value={observedAt} />
          </p>
        )}
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

function DataQualityNotice({ detail }: { detail: string }) {
  return (
    <div role="status" style={{ ...card, borderColor: 'var(--warning, var(--line))', display: 'grid', gap: 4 }}>
      <strong style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--ink)' }}>
        Partial Builder data
      </strong>
      <span style={{ ...bodyText, overflowWrap: 'anywhere' }}>{detail}</span>
    </div>
  )
}

function BuilderNextActionCard({
  snapshot,
  onOpenAllPackets,
  allPacketsButtonRef,
}: {
  snapshot: BuilderStatusSnapshot
  onOpenAllPackets: () => void
  allPacketsButtonRef: React.RefObject<HTMLButtonElement | null>
}) {
  const nextAction = deriveNextAction(snapshot)
  return (
    <section style={{ ...card, display: 'grid', gap: 8 }} aria-label="Builder next action">
      <div style={cardHeader}>
        <div style={cardTitle}>next action</div>
      </div>
      <strong style={{ fontFamily: 'var(--font-body)', color: 'var(--ink)' }}>{nextAction.label}</strong>
      <p style={{ ...bodyText, margin: 0, overflowWrap: 'anywhere' }}>{nextAction.detail}</p>
      <div>
        <button ref={allPacketsButtonRef} type="button" onClick={onOpenAllPackets} style={actionButton}>
          View all packets
        </button>
      </div>
    </section>
  )
}

function BuilderControls({
  snapshot,
  selection,
  onRefresh,
}: {
  snapshot: BuilderStatusSnapshot
  selection: PacketSelection | null
  onRefresh: () => void
}) {
  const action = useBuilderAction()
  const [busy, setBusy] = useState(false)

  const pausedInitiatives = snapshot.initiatives.filter((i) => i.state === 'paused')
  const activeInitiatives = snapshot.initiatives.filter((i) => i.state === 'active')
  const zombiePackets = snapshot.initiatives.flatMap((i) =>
    i.packets.filter((p) => p.task_state === 'cancelled' || p.task_state === 'failed')
  )

  const runAction = (builderAction: string, initiativeId?: string, packetId?: string) => {
    setBusy(true)
    action.mutate(
      { action: builderAction, initiativeId, packetId },
      {
        onSettled: () => setBusy(false),
      },
    )
  }

  if (
    activeInitiatives.length === 0 &&
    pausedInitiatives.length === 0 &&
    zombiePackets.length === 0
  ) {
    return null
  }

  return (
    <section style={{ ...card, display: 'grid', gap: 12 }} aria-label="Builder controls">
      <div style={cardHeader}>
        <div style={cardTitle}>controls</div>
      </div>

      {pausedInitiatives.map((initiative) => (
        <div key={initiative.initiative_id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink)', flex: 1, minWidth: 120 }}>
            {initiative.title} is paused
          </span>
          {initiative.pause_reason && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', flex: 1, minWidth: 120 }}>
              {initiative.pause_reason}
            </span>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => runAction('resume', initiative.initiative_id)}
            style={actionButton}
          >
            resume
          </button>
        </div>
      ))}

      {activeInitiatives.length > 0 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink)', flex: 1 }}>
            {activeInitiatives.map((i) => i.title).join(', ')}
          </span>
        </div>
      )}

      {zombiePackets.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }}>
            {zombiePackets.length} dead task{zombiePackets.length === 1 ? '' : 's'} — cancelled or failed
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={() => runAction('cleanup')}
            style={{ ...actionButton, alignSelf: 'flex-start', borderColor: 'var(--c-red)', color: 'var(--c-red)' }}
          >
            {busy ? '…' : 'clean up dead work'}
          </button>
        </div>
      )}
    </section>
  )
}

function AllPacketsModal({
  snapshot,
  onClose,
  onSelectPacket,
}: {
  snapshot: BuilderStatusSnapshot
  onClose: () => void
  onSelectPacket: (selection: PacketSelection) => void
}) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="all-builder-packets-heading"
      onKeyDown={(event) => {
        if (event.key === 'Escape') onClose()
      }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 20,
        display: 'grid',
        placeItems: 'center',
        padding: 16,
        background: 'rgba(0, 0, 0, 0.55)',
      }}
    >
      <section style={{ ...card, width: 'min(860px, 100%)', maxHeight: 'min(760px, 100%)', overflow: 'auto', display: 'grid', gap: 14 }}>
        <header style={cardHeader}>
          <div>
            <h2
              ref={headingRef}
              id="all-builder-packets-heading"
              tabIndex={-1}
              style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--ink)' }}
            >
              All Builder packets
            </h2>
            <p style={{ ...bodyText, margin: '4px 0 0' }}>
              Read-only status from durable Builder records.
            </p>
          </div>
          <button type="button" onClick={onClose} style={actionButton}>Close</button>
        </header>
        {snapshot.initiatives.map((initiative) => (
          <section key={initiative.initiative_id} style={{ ...itemCard, display: 'grid', gap: 8 }}>
            <div style={cardHeader}>
              <strong style={{ fontFamily: 'var(--font-body)', color: 'var(--ink)' }}>{initiative.title}</strong>
              <span style={cardMeta}>{displayState(initiative.state)} · {initiative.counts.total} packets</span>
            </div>
            {initiative.pause_reason && (
              <p style={{ ...bodyText, margin: 0, overflowWrap: 'anywhere' }}>{initiative.pause_reason}</p>
            )}
            {sortPacketsForAttention(initiative.packets).map((packet) => (
              <button
                key={`${packet.initiative_id}:${packet.packet_id}`}
                type="button"
                onClick={() => onSelectPacket({ initiativeId: packet.initiative_id, packetId: packet.packet_id })}
                aria-label={`Open packet ${packet.title} from all packets`}
                style={{ ...itemCard, cursor: 'pointer', textAlign: 'left', color: 'var(--ink)', display: 'grid', gap: 4 }}
              >
                <span style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600 }}>{packet.title}</span>
                <span style={cardMeta}>{packetSummary(packet)} · {eligibilityLabel(packet)}</span>
                <span style={{ ...cardMeta, opacity: 0.8 }}>{packet.packet_id}</span>
              </button>
            ))}
          </section>
        ))}
      </section>
    </div>
  )
}

function BuilderOverview({
  snapshot,
  onSelectPacket,
  registerPacketButton,
}: {
  snapshot: BuilderStatusSnapshot
  onSelectPacket: (selection: PacketSelection) => void
  registerPacketButton: (
    selection: PacketSelection,
    node: HTMLButtonElement | null,
  ) => void
}) {
  return (
    <>
      <div style={detailGrid}>
        <Metric label="needs attention" value={attentionCount(snapshot)} />
        <Metric label="active work" value={activePacketCount(snapshot)} />
        <Metric label="queued work" value={snapshot.queue.queued} />
        <Metric label="completed" value={snapshot.queue.done} />
      </div>
      {snapshot.initiatives.map((initiative) => (
        <section key={initiative.initiative_id} style={{ ...card, display: 'grid', gap: 12, minWidth: 0 }}>
          <div style={cardHeader}>
            <div style={{ minWidth: 0 }}>
              <div style={{ ...cardTitle, overflowWrap: 'anywhere' }}>{initiative.title}</div>
              <div style={{ ...cardMeta, marginTop: 4 }}>
                {displayState(initiative.state)}
                {initiative.data_quality.state === 'partial' ? ' · partial data' : ''}
              </div>
            </div>
            <span style={cardMeta}>{initiative.counts.total} packets</span>
          </div>
          {initiative.pause_reason && (
            <p style={{ ...bodyText, margin: 0, overflowWrap: 'anywhere' }}>
              {initiative.pause_reason}
            </p>
          )}
          <div style={{ display: 'grid', gap: 8, minWidth: 0 }}>
            {sortPacketsForAttention(initiative.packets).map((packet) => (
              <button
                key={`${packet.initiative_id}:${packet.packet_id}`}
                ref={(node) => registerPacketButton({
                  initiativeId: packet.initiative_id,
                  packetId: packet.packet_id,
                }, node)}
                type="button"
                onClick={() => onSelectPacket({
                  initiativeId: packet.initiative_id,
                  packetId: packet.packet_id,
                })}
                aria-label={`View packet ${packet.title}`}
                style={{
                  ...itemCard,
                  cursor: 'pointer',
                  textAlign: 'left',
                  color: 'var(--ink)',
                  display: 'grid',
                  gap: 5,
                  minWidth: 0,
                  overflowWrap: 'anywhere',
                }}
              >
                <span style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600 }}>
                  {packet.title}
                </span>
                <span style={cardMeta}>
                  {packetSummary(packet)}
                  {packet.attempt_history[0]
                    ? ` · attempt ${packet.attempt_history[0].number}`
                    : ''}
                </span>
                <span style={{ ...cardMeta, opacity: 0.8 }}>{packet.packet_id}</span>
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
  degradedReason,
  onBack,
  onHome,
}: {
  packet: BuilderPacketStatus
  stale: boolean
  degradedReason?: string | null
  onBack: () => void
  onHome?: () => void
}) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <section style={surfaceLayout}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ ...cardMeta, margin: 0 }}>{packet.packet_id}</p>
          <h2
            ref={headingRef}
            tabIndex={-1}
            style={{ margin: '4px 0 0', fontFamily: 'var(--font-display)', fontSize: 28, color: 'var(--ink)', overflowWrap: 'anywhere' }}
          >
            {packet.title}
          </h2>
          {packet.objective && (
            <p style={{ ...bodyText, margin: '8px 0 0', maxWidth: 760, overflowWrap: 'anywhere' }}>
              {packet.objective}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={onBack} style={actionButton}>Back to overview</button>
          {onHome && <button type="button" onClick={onHome} style={actionButton}>Back to home</button>}
        </div>
      </header>
      {stale && <StaleNotice />}
      {degradedReason && <DataQualityNotice detail={degradedReason} />}
      {packet.data_quality.state === 'partial' && (
        <DataQualityNotice detail={packet.data_quality.issues.join(' ')} />
      )}
      <div style={detailGrid}>
        <Metric label="task state" value={displayState(packet.task_state ?? 'unavailable')} />
        <Metric label="attempt budget" value={budgetLabel(packet)} />
        <Metric label="eligibility" value={displayState(packet.eligibility.state)} />
        <Metric label="last update" value={<TimeValue value={packet.updated_at} fallback="unavailable" />} />
      </div>
      <div style={{ ...card, display: 'grid', gap: 14, minWidth: 0 }}>
        <div style={cardHeader}><span style={cardTitle}>Current status</span></div>
        <StatusDetail label="Failure classification" value={failureLabel(packet.failure_kind)} />
        <StatusDetail label="Blocked reason" value={packet.blocked_reason} />
        <StatusDetail label="Last error" value={packet.last_error} />
        {packet.depends_on.length > 0 && (
          <StatusDetail label="Dependencies" value={packet.depends_on.join(', ')} />
        )}
        {packet.eligibility.blocked_by.length > 0 && (
          <StatusDetail label="Blocked by" value={packet.eligibility.blocked_by.join(', ')} />
        )}
        <StatusDetail label="Latest durable event" value={eventSummary(packet)} />
      </div>
      <AttemptHistory packet={packet} />
      <div style={detailGrid}>
        <RunCard packet={packet} />
        <ExecutionContextCard packet={packet} />
        <PublicationCard packet={packet} />
      </div>
      <InvestigationCard packet={packet} />
    </section>
  )
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div style={{ ...card, display: 'grid', gap: 4, minWidth: 0 }}>
      <span style={cardMeta}>{label}</span>
      <strong style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--ink)', overflowWrap: 'anywhere' }}>
        {typeof value === 'number' && label === 'needs attention'
          ? `${value} needs attention`
          : value}
      </strong>
    </div>
  )
}

function StatusDetail({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div style={{ display: 'grid', gap: 3, minWidth: 0 }}>
      <span style={cardMeta}>{label}</span>
      <span style={{ ...bodyText, color: 'var(--ink)', overflowWrap: 'anywhere' }}>{value}</span>
    </div>
  )
}

function AttemptHistory({ packet }: { packet: BuilderPacketStatus }) {
  return (
    <section style={{ ...card, display: 'grid', gap: 12, minWidth: 0 }}>
      <div style={cardHeader}>
        <h3 style={{ ...cardTitle, margin: 0 }}>Attempt history</h3>
        <span style={cardMeta}>{packet.attempt_count} total</span>
      </div>
      {packet.attempt_history_truncated && (
        <p role="status" style={{ ...bodyText, margin: 0 }}>
          Showing latest {packet.attempt_history.length} of {packet.attempt_count} attempts.
        </p>
      )}
      {packet.attempt_history.length > 0 ? (
        <ol style={{ display: 'grid', gap: 8, margin: 0, padding: 0, listStyle: 'none' }}>
          {packet.attempt_history.map((attempt, index) => (
            <li key={attempt.id}>
              <AttemptCard attempt={attempt} latest={index === 0} />
            </li>
          ))}
        </ol>
      ) : (
        <p style={{ ...emptyState, margin: 0 }}>No attempts have been recorded.</p>
      )}
    </section>
  )
}

function AttemptCard({ attempt, latest }: { attempt: BuilderAttemptStatus; latest: boolean }) {
  const budgetText = attempt.counts_toward_budget
    ? 'Consumed retry budget'
    : attempt.outcome === 'crashed'
      ? 'Infrastructure crash · did not consume retry budget'
      : attempt.outcome === null
        ? 'Retry budget pending'
        : 'Did not consume retry budget'
  return (
    <article style={{ ...itemCard, display: 'grid', gap: 7, minWidth: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontFamily: 'var(--font-body)', fontSize: 13 }}>
          Attempt #{attempt.number}
        </strong>
        <span style={cardMeta}>
          {latest ? 'latest · ' : ''}{attempt.outcome ? displayState(attempt.outcome) : 'in progress'}
        </span>
      </div>
      <span style={cardMeta}>{budgetText}</span>
      <span style={cardMeta}>Updated <TimeValue value={attempt.updated_at} fallback="unavailable" /></span>
      {attempt.implementation && (
        <EvidenceBlock title="Implementation" status={attempt.implementation.status}>
          {attempt.implementation.summary && <p style={{ ...bodyText, margin: 0 }}>{attempt.implementation.summary}</p>}
          {attempt.implementation.diff_summary && <p style={{ ...cardMeta, margin: 0 }}>{attempt.implementation.diff_summary}</p>}
        </EvidenceBlock>
      )}
      {attempt.validation && (
        <EvidenceBlock title="Validation" status={attempt.validation.status}>
          <p style={{ ...bodyText, margin: 0 }}>{attempt.validation.summary}</p>
        </EvidenceBlock>
      )}
      {attempt.review && (
        <EvidenceBlock title="Review" status={reviewLabel(attempt.review.verdict)}>
          {attempt.review.summary && <p style={{ ...bodyText, margin: 0 }}>{attempt.review.summary}</p>}
          {attempt.review.findings.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {attempt.review.findings.map((finding, index) => (
                <li key={`${finding.severity ?? 'finding'}-${index}`} style={{ ...bodyText, marginTop: 3 }}>
                  {finding.severity && <span style={cardMeta}>{displayState(finding.severity)}: </span>}
                  <span>{finding.note}</span>
                </li>
              ))}
            </ul>
          )}
          {attempt.review.findings_truncated && <span style={cardMeta}>Additional findings omitted.</span>}
        </EvidenceBlock>
      )}
      {attempt.data_quality.state === 'partial' && (
        <span style={{ ...bodyText, color: 'var(--warning, var(--ink-2))' }}>
          Partial evidence: {attempt.data_quality.issues.join(' ')}
        </span>
      )}
    </article>
  )
}

function EvidenceBlock({
  title,
  status,
  children,
}: {
  title: string
  status: string | null
  children: ReactNode
}) {
  return (
    <div style={{ display: 'grid', gap: 4, borderTop: '1px solid var(--line)', paddingTop: 7 }}>
      <span style={cardMeta}>{title}{status ? ` · ${displayState(status)}` : ' · not recorded'}</span>
      {children}
    </div>
  )
}

function RunCard({ packet }: { packet: BuilderPacketStatus }) {
  const run = packet.run
  return (
    <div style={{ ...card, display: 'grid', gap: 6, minWidth: 0 }}>
      <span style={cardTitle}>Latest run</span>
      {run ? (
        <>
          <span style={bodyText}>{displayState(run.state)}</span>
          <span style={cardMeta}>Started <TimeValue value={run.started_at} fallback="unavailable" /></span>
          {run.ended_at && <span style={cardMeta}>Ended <TimeValue value={run.ended_at} /></span>}
          {run.started_at && (
            <span style={cardMeta}>Duration {durationLabel(run.started_at, run.ended_at)}</span>
          )}
          {run.exit_code !== null && <span style={cardMeta}>Exit code {run.exit_code}</span>}
        </>
      ) : <span style={bodyText}>No run recorded.</span>}
    </div>
  )
}

function ExecutionContextCard({ packet }: { packet: BuilderPacketStatus }) {
  return (
    <div style={{ ...card, display: 'grid', gap: 6, minWidth: 0 }}>
      <span style={cardTitle}>Execution context</span>
      {packet.lease ? (
        <>
          <span style={bodyText}>Active lease #{packet.lease.id}</span>
          {packet.lease.worker_id && <span style={cardMeta}>Worker {packet.lease.worker_id}</span>}
          {packet.lease.branch && <span style={{ ...cardMeta, overflowWrap: 'anywhere' }}>Branch {packet.lease.branch}</span>}
          {packet.lease.created_at && <span style={cardMeta}>Claimed <TimeValue value={packet.lease.created_at} /></span>}
        </>
      ) : <span style={bodyText}>No active branch lease.</span>}
      {packet.base_sha && <span style={cardMeta}>Base {packet.base_sha.slice(0, 12)}</span>}
    </div>
  )
}

function PublicationCard({ packet }: { packet: BuilderPacketStatus }) {
  const publication = packet.publication
  return (
    <div style={{ ...card, display: 'grid', gap: 6, minWidth: 0 }}>
      <span style={cardTitle}>Publication</span>
      {publication ? (
        <>
          <span style={bodyText}>{publication.merged ? 'Merged' : `Pull request #${publication.pr_number}`}</span>
          <span style={cardMeta}>checks: {displayState(publication.checks_state ?? 'unknown')}</span>
          <span style={cardMeta}>review: {displayState(publication.review_state ?? 'unknown')}</span>
          {publication.updated_at && <span style={cardMeta}>Updated <TimeValue value={publication.updated_at} /></span>}
          {publication.pr_url && (
            <a href={publication.pr_url} target="_blank" rel="noreferrer" style={{ ...bodyText, color: 'var(--primary)', overflowWrap: 'anywhere' }}>
              Open pull request #{publication.pr_number}
            </a>
          )}
        </>
      ) : <span style={bodyText}>No pull request recorded.</span>}
    </div>
  )
}

function InvestigationCard({ packet }: { packet: BuilderPacketStatus }) {
  return (
    <section style={{ ...card, display: 'grid', gap: 10, minWidth: 0 }}>
      <div style={cardHeader}><h3 style={{ ...cardTitle, margin: 0 }}>Investigation sources</h3></div>
      <p style={{ ...bodyText, margin: 0 }}>
        Logs and artifacts remain unavailable until the gateway can serve bounded, redacted durable resources instead of local paths.
      </p>
      <StatusDetail label="Logs" value={packet.investigation.logs.reason} />
      <StatusDetail label="Artifacts" value={packet.investigation.artifacts.reason} />
    </section>
  )
}

function TimeValue({ value, fallback = 'unknown' }: { value: string | null | undefined; fallback?: string }) {
  if (!value) return <>{fallback}</>
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return <>{fallback}</>
  return <time dateTime={value}>{new Date(timestamp).toLocaleString()}</time>
}

function durationLabel(start: string, end: string | null): string {
  const startTime = Date.parse(start)
  const endTime = end ? Date.parse(end) : Date.now()
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime < startTime) {
    return 'unavailable'
  }
  const seconds = Math.round((endTime - startTime) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`
}

function budgetLabel(packet: BuilderPacketStatus): string {
  if (packet.budget.max === null) return `${packet.budget.used}/unknown`
  return `${packet.budget.used}/${packet.budget.max}`
}

function sortPacketsForAttention(packets: BuilderPacketStatus[]): BuilderPacketStatus[] {
  return packets
    .map((packet, index) => ({ packet, index }))
    .sort((left, right) => {
      const priority = packetPriority(left.packet) - packetPriority(right.packet)
      return priority || left.index - right.index
    })
    .map(({ packet }) => packet)
}

function packetPriority(packet: BuilderPacketStatus): number {
  if (packetNeedsAttention(packet)) return 0
  if (isPacketActive(packet)) return 1
  return 2
}

function packetNeedsAttention(packet: BuilderPacketStatus): boolean {
  return packet.task_state === 'blocked'
    || packet.task_state === 'failed'
    || packet.budget.exhausted === true
    || packet.failure_kind !== null
    || packet.data_quality.state === 'partial'
}

function isPacketActive(packet: BuilderPacketStatus): boolean {
  return packet.run?.state === 'starting'
    || packet.run?.state === 'running'
    || packet.run?.state === 'cancel_requested'
}

function attentionCount(snapshot: BuilderStatusSnapshot): number {
  return snapshot.initiatives
    .flatMap((initiative) => initiative.packets)
    .filter(packetNeedsAttention).length
}

function activePacketCount(snapshot: BuilderStatusSnapshot): number {
  return snapshot.initiatives
    .flatMap((initiative) => initiative.packets)
    .filter(isPacketActive).length
}

function findPacket(
  snapshot: BuilderStatusSnapshot | null | undefined,
  selection: PacketSelection,
): BuilderPacketStatus | null {
  const initiative = snapshot?.initiatives.find(
    (candidate) => candidate.initiative_id === selection.initiativeId,
  )
  return initiative?.packets.find(
    (packet) => packet.packet_id === selection.packetId,
  ) ?? null
}

function packetSelectionKey(selection: PacketSelection): string {
  return `${selection.initiativeId}\u0000${selection.packetId}`
}

function builderGlanceLabel(
  fact: RuntimeFact<BuilderStatusSnapshot> | undefined,
  isLoading: boolean,
  attention: number,
  active: number,
): string {
  if (isLoading && !fact) return 'loading'
  if (!fact?.value || fact.state === 'unavailable' || fact.state === 'unknown') return 'unavailable'
  if (fact.state === 'degraded') return 'partial data'
  if (fact.state === 'stale' || isExpired(fact.valid_until)) return 'stale'
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
  if (fact.state === 'degraded' && fact.reason) return fact.reason
  if (fact.state === 'stale' || isExpired(fact.valid_until)) {
    return 'The last known Builder snapshot is visible, but it is past its freshness window.'
  }
  const snapshot = fact.value
  const active = activePacketCount(snapshot)
  if (active) return `${active} packet${active === 1 ? '' : 's'} active. This surface refreshes more often while work is running.`
  if (snapshot.queue.total === 0) return 'No Builder work is recorded yet.'
  return `${snapshot.queue.done} complete, ${snapshot.queue.queued} queued, ${snapshot.queue.blocked} blocked.`
}

function packetSummary(packet: BuilderPacketStatus): string {
  return failureLabel(packet.failure_kind)
    || displayState(packet.task_state ?? packet.eligibility.state)
}

function eligibilityLabel(packet: BuilderPacketStatus): string {
  if (packet.eligibility.blocked_by.length > 0) {
    return `blocked by ${packet.eligibility.blocked_by.join(', ')}`
  }
  return displayState(packet.eligibility.state)
}

function deriveNextAction(snapshot: BuilderStatusSnapshot): BuilderNextAction {
  const pausedWithReason = snapshot.initiatives.find(
    (initiative) => initiative.state === 'paused' && initiative.pause_reason,
  )
  if (pausedWithReason) {
    return {
      label: `Needs a decision: ${pausedWithReason.title}`,
      detail: pausedWithReason.pause_reason!,
    }
  }

  const attentionPacket = snapshot.initiatives
    .flatMap((initiative) => initiative.packets)
    .find(packetNeedsAttention)
  if (attentionPacket) {
    const reason = attentionPacket.blocked_reason
      || attentionPacket.last_error
      || failureLabel(attentionPacket.failure_kind)
      || 'This packet needs investigation before work can continue.'
    return {
      label: `Investigate: ${attentionPacket.title}`,
      detail: reason,
    }
  }

  const activePacket = snapshot.initiatives
    .flatMap((initiative) => initiative.packets)
    .find(isPacketActive)
  if (activePacket) {
    return {
      label: `Work is running: ${activePacket.title}`,
      detail: 'This surface will refresh while the durable Builder run reports activity.',
    }
  }

  const readyInitiative = snapshot.initiatives.find(
    (initiative) => initiative.state === 'active' && initiative.next_packet,
  )
  if (readyInitiative) {
    return {
      label: `Ready for an authorized run: ${readyInitiative.next_packet}`,
      detail: `${readyInitiative.title} has an eligible next packet. This UI does not start Builder work.`,
    }
  }

  if (snapshot.queue.total > 0 && snapshot.queue.done === snapshot.queue.total) {
    return {
      label: 'No action needed',
      detail: 'Every recorded Builder packet is complete.',
    }
  }

  return {
    label: 'No eligible packet is reported',
    detail: 'Open all packets to inspect durable state, dependencies, and the latest event.',
  }
}

function eventSummary(packet: BuilderPacketStatus): string | null {
  if (!packet.last_event) return null
  const label = displayState(packet.last_event.type)
  const budget = packet.last_event.counts_toward_budget === false
    ? ' · did not consume retry budget'
    : ''
  return packet.last_event.reason
    ? `${label}: ${packet.last_event.reason}${budget}`
    : `${label}${budget}`
}

function failureLabel(kind: BuilderFailureKind | null): string | null {
  const labels: Record<BuilderFailureKind, string> = {
    implementation: 'Implementation failure',
    infrastructure: 'Infrastructure failure',
    identity: 'Identity failure',
    scope: 'Scope failure',
    validation: 'Validation failure',
    review: 'Review failure',
    cancelled: 'Cancelled',
    blocked: 'Blocked',
    exhausted: 'Attempt budget exhausted',
  }
  return kind ? labels[kind] : null
}

function reviewLabel(verdict: BuilderAttemptStatus['review_verdict']): string | null {
  if (verdict === 'reject') return 'Review rejected'
  if (verdict === 'request_changes') return 'Review changes requested'
  if (verdict === 'approve') return 'Review approved'
  return null
}

function displayState(value: string): string {
  return value.replace(/_/g, ' ')
}

/** Per-initiative progress cards showing state, progress, blocker, and next action. */
function BuilderInitiativeCards({ snapshot }: { snapshot: NonNullable<BuilderStatusSnapshot> }) {
  const initiatives = snapshot.initiatives
  if (!initiatives.length) return null

  return (
    <div style={detailGrid}>
      {initiatives.map((init) => {
        const packets = init.packets ?? []
        const done = packets.filter((p) => p.task_state === 'done').length
        const total = packets.length
        const progress = total > 0 ? Math.round((done / total) * 100) : 0
        const nextPacket = init.next_packet
          ? packets.find((p) => p.packet_id === init.next_packet)
          : null
        const blockedPacket = packets.find(
          (p) => p.task_state === 'blocked' || p.eligibility.state === 'blocked'
        )
        const inFlight = packets.filter(
          (p) => p.task_state === 'running' || p.task_state === 'claimed'
        )
        const isComplete = init.state === 'completed'
        const isPaused = init.state === 'paused'
        const isFailed = init.state === 'failed'

        const statusColor = isComplete
          ? 'var(--c-green)'
          : isFailed
          ? 'var(--c-red)'
          : isPaused
          ? 'var(--c-yellow)'
          : 'var(--c-blue)'

        const statusLabel = isComplete
          ? 'done'
          : isFailed
          ? 'failed'
          : isPaused
          ? 'paused'
          : inFlight.length > 0
          ? `${inFlight.length} running`
          : done > 0
          ? `${done}/${total}`
          : 'queued'

        return (
          <div
            key={init.initiative_id}
            style={{
              ...card,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              borderLeft: `3px solid ${statusColor}`,
            }}
            aria-label={`${init.title}: ${statusLabel}`}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {init.title}
              </span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                fontWeight: 700,
                color: statusColor,
                flexShrink: 0,
                padding: '2px 8px',
                borderRadius: 999,
                background: `${statusColor}15`,
              }}>
                {statusLabel}
              </span>
            </div>

            {!isComplete && !isFailed && total > 0 && (
              <div style={{ height: 3, borderRadius: 99, background: 'var(--surface-2)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: `${Math.max(2, progress)}%`,
                  background: statusColor,
                  borderRadius: 99,
                  transition: 'width 0.3s ease',
                }} />
              </div>
            )}

            {isPaused && init.pause_reason && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', margin: 0, lineHeight: 1.5 }}>
                Paused: {init.pause_reason.slice(0, 120)}
              </p>
            )}

            {blockedPacket && !isComplete && !isPaused && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-red)', margin: 0, lineHeight: 1.5 }}>
                Blocked: {blockedPacket.packet_id}
                {blockedPacket.blocked_reason ? ` — ${blockedPacket.blocked_reason.slice(0, 100)}` : ''}
              </p>
            )}

            {nextPacket && !isComplete && !isPaused && !isFailed && !blockedPacket && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-blue)', margin: 0, lineHeight: 1.5 }}>
                Next: {nextPacket.title ?? nextPacket.packet_id}
              </p>
            )}

            {init.counts.exhausted > 0 && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-yellow)', margin: 0 }}>
                {init.counts.exhausted} packet{init.counts.exhausted > 1 ? 's' : ''} exhausted
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function isExpired(validUntil: string | undefined): boolean {
  if (!validUntil) return false
  const timestamp = Date.parse(validUntil)
  return Number.isFinite(timestamp) && timestamp < Date.now()
}
