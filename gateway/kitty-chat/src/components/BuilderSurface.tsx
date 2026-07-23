'use client'

import { useEffect, useRef, useState, type CSSProperties, type ReactNode, useCallback } from 'react'

import { bodyText, card, cardHeader, cardMeta, cardTitle, emptyState, itemCard } from '@/lib/ui'
import { useGatewayRuntimeManifest } from '@/lib/queries'
import { streamChat } from '@/lib/chat-client'
import { startBuild } from '@/lib/gateway'
import type {
  BuilderAttemptStatus,
  BuilderFailureKind,
  BuilderPacketStatus,
  BuilderStatusSnapshot,
  RuntimeFact,
} from '@/lib/gateway'
import type { Message } from '@/lib/types'

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
      <p style={{ ...cardMeta, margin: 0 }}>
        Builder runs automated code tasks: implement, validate, review, and publish.
      </p>
      <div>
        <button type="button" onClick={onOpen} style={actionButton}>
          Open Builder
        </button>
      </div>
    </section>
  )
}

/** Thin status banner for the top of the home/chat surface. */
export function BuilderStatusBanner({ onOpen }: { onOpen?: () => void }) {
  const query = useGatewayRuntimeManifest()
  const fact = query.data?.execution.builder
  const snapshot = fact?.value
  const attention = snapshot ? attentionCount(snapshot) : 0
  const active = snapshot ? activePacketCount(snapshot) : 0

  const total = snapshot ? snapshot.queue.total : 0
  if (query.isLoading) return null
  if (attention === 0 && active === 0 && total === 0) return null

  const dot = attention > 0
    ? 'var(--c-red)'
    : active > 0
      ? 'var(--c-green)'
      : 'var(--ink-2)'
  const label = attention > 0
    ? `${attention} need attention`
    : active > 0
      ? `${active} running`
      : `${total} in queue`

  return (
    <button
      type="button"
      onClick={onOpen}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '4px 10px',
        background: 'var(--surface-2)',
        border: '1px solid var(--line)',
        borderRadius: 99,
        cursor: onOpen ? 'pointer' : 'default',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--ink-2)',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot, flexShrink: 0 }} />
      builder · {label}
    </button>
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
      <StartBuildForm />
      {stale && <StaleNotice />}
      {fact.state === 'degraded' && fact.reason && (
        <DataQualityNotice detail={fact.reason} />
      )}
      {snapshot.initiatives.length === 0 ? (
        <section style={{ ...card, display: 'grid', gap: 12, textAlign: 'center', padding: '24px 16px' }} aria-label="Builder empty state">
          <strong style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--ink)' }}>
            ready to build something?
          </strong>
          <p style={{ ...bodyText, margin: 0, maxWidth: 520, justifySelf: 'center' }}>
            Describe what you want Builder to implement in the form above. It will plan the work, write the code, run tests, and open a pull request.
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => {
                const ta = document.querySelector<HTMLTextAreaElement>('[data-builder-goal]')
                ta?.focus()
                ta?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              }}
              style={{ ...actionButton, background: 'var(--primary, var(--c-blue))', color: 'white' }}
            >
              Start your first build
            </button>
          </div>
          <p style={{ ...cardMeta, margin: 0 }}>
            Or try an example: “Add a /health endpoint that returns 200 OK”
          </p>
        </section>
      ) : (
        <>
          <BuilderNextActionCard
            snapshot={snapshot}
            onOpenAllPackets={() => setAllPacketsOpen(true)}
            allPacketsButtonRef={allPacketsButtonRef}
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
      <BuilderChat />
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
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 12, flexWrap: 'wrap' }}>
      <div style={{ minWidth: 0 }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>
          Builder
        </h1>
        <p style={{ ...bodyText, margin: '4px 0 0' }}>
          Automated code execution system. Packets are units of work that get queued, executed, validated, and reviewed.
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

function HowBuilderWorks() {
  const [open, setOpen] = useState(false)
  return (
    <section style={{ ...card, display: 'grid', gap: 8 }} aria-label="How Builder works">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          padding: 0,
          fontFamily: 'var(--font-body)',
          color: 'var(--ink)',
        }}
      >
        <strong style={{ fontSize: 14 }}>how builder works</strong>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <ol style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 6, color: 'var(--ink)', fontFamily: 'var(--font-body)', fontSize: 13, lineHeight: 1.5 }}>
          <li><strong>Describe a goal</strong> — e.g., “add a /health endpoint”.</li>
          <li><strong>Builder plans packets</strong> — small units of work.</li>
          <li><strong>A worker implements</strong> the code in an isolated branch.</li>
          <li><strong>Validators run tests</strong>, reviewers check quality.</li>
          <li><strong>A pull request</strong> is created and merged.</li>
        </ol>
      )}
    </section>
  )
}

function StartBuildForm() {
  const [goal, setGoal] = useState('')
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleStart = useCallback(async () => {
    if (!goal.trim() || isStarting) return
    setIsStarting(true)
    setError(null)
    setSuccess(null)

    try {
      const result = await startBuild(goal.trim())
      setSuccess(`Build started: ${result.build_id}`)
      setGoal('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start build')
    } finally {
      setIsStarting(false)
    }
  }, [goal, isStarting])

  return (
    <section style={{ ...card, display: 'grid', gap: 8 }} aria-label="Start new build">
      <div style={cardHeader}>
        <div style={cardTitle}>start new build</div>
        <span style={cardMeta}>submit a goal for Builder to execute</span>
      </div>
      <p style={{ ...bodyText, margin: 0 }}>
        Describe what you want Builder to implement. It will create a plan, execute the code changes, validate, and optionally create a pull request.
      </p>
      <div style={{ display: 'grid', gap: 8 }}>
        <textarea
          data-builder-goal
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="e.g., Add a /health endpoint that returns 200 OK"
          rows={3}
          disabled={isStarting}
          style={{
            resize: 'vertical',
            border: '1px solid var(--line)',
            borderRadius: 4,
            padding: '8px 10px',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            background: 'var(--bg)',
            color: 'var(--ink)',
            outline: 'none',
            lineHeight: 1.5,
          }}
        />
        {error && (
          <p style={{ ...bodyText, margin: 0, color: 'var(--c-red)' }}>{error}</p>
        )}
        {success && (
          <p style={{ ...bodyText, margin: 0, color: 'var(--c-green)' }}>{success}</p>
        )}
        <div>
          <button
            type="button"
            onClick={handleStart}
            disabled={!goal.trim() || isStarting}
            style={{
              ...actionButton,
              background: goal.trim() ? 'var(--primary, var(--c-blue))' : 'var(--surface)',
              color: goal.trim() ? 'white' : 'var(--ink)',
              opacity: goal.trim() ? 1 : 0.5,
            }}
          >
            {isStarting ? 'Starting...' : 'Start Build'}
          </button>
        </div>
      </div>
    </section>
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
        <span style={cardMeta}>what needs your attention</span>
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
              Complete list of all work units across all initiatives. Click a packet to see detailed status.
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
        <Metric label="needs attention" value={attentionCount(snapshot)} tooltip="Packets that are blocked, failed, or need investigation before work can continue" />
        <Metric label="active work" value={activePacketCount(snapshot)} tooltip="Packets currently being executed by a worker" />
        <Metric label="queued work" value={snapshot.queue.queued} tooltip="Packets waiting to be picked up by a worker" />
        <Metric label="completed" value={snapshot.queue.done} tooltip="Packets that have finished successfully" />
      </div>
      <StatusLegend />
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
                  display: 'flex',
                  alignItems: 'start',
                  gap: 8,
                  minWidth: 0,
                  overflowWrap: 'anywhere',
                }}
              >
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: packetStatusColor(packet),
                  flexShrink: 0,
                  marginTop: 5,
                }} />
                <div style={{ display: 'grid', gap: 5, minWidth: 0, flex: 1 }}>
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
                </div>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
            <CopyableText value={packet.packet_id} label="packet_id" />
          </div>
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
        <Metric label="task state" value={displayState(packet.task_state ?? 'unavailable')} tooltip="Current execution state of this packet (queued, running, blocked, etc.)" />
        <Metric label="attempt budget" value={budgetLabel(packet)} tooltip="How many retry attempts have been used out of the maximum allowed" />
        <Metric label="eligibility" value={displayState(packet.eligibility.state)} tooltip="Whether this packet can be picked up by a worker" />
        <Metric label="last update" value={<TimeValue value={packet.updated_at} fallback="unavailable" />} tooltip="When this packet's status was last updated" />
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

function Metric({ label, value, tooltip }: { label: string; value: ReactNode; tooltip?: string }) {
  return (
    <div style={{ ...card, display: 'grid', gap: 4, minWidth: 0 }} title={tooltip}>
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

function CopyableText({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      /* clipboard unavailable — silent */
    }
  }, [value])

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-mono)' }}>
      {label && <span style={{ color: 'var(--ink-2)', fontSize: 11 }}>{label}</span>}
      <code style={{ color: 'var(--ink)', fontSize: 11, background: 'var(--surface-2)', padding: '2px 6px', borderRadius: 3, overflowWrap: 'anywhere' }}>
        {value}
      </code>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={label ? `Copy ${label}` : 'Copy value'}
        style={{
          border: '1px solid var(--line)',
          borderRadius: 3,
          background: 'var(--surface)',
          padding: '2px 6px',
          fontSize: 10,
          cursor: 'pointer',
          color: 'var(--ink-2)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {copied ? 'copied' : 'copy'}
      </button>
    </span>
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
    <div style={{ ...card, display: 'grid', gap: 8, minWidth: 0 }}>
      <span style={cardTitle}>Execution context</span>
      {packet.lease ? (
        <>
          <span style={bodyText}>Active lease #{packet.lease.id}</span>
          {packet.lease.worker_id && <CopyableText value={packet.lease.worker_id} label="worker" />}
          {packet.lease.branch && <CopyableText value={packet.lease.branch} label="branch" />}
          {packet.lease.created_at && <span style={cardMeta}>Claimed <TimeValue value={packet.lease.created_at} /></span>}
        </>
      ) : <span style={bodyText}>No active branch lease.</span>}
      {packet.base_sha && <CopyableText value={packet.base_sha} label="base_sha" />}
    </div>
  )
}

function PublicationCard({ packet }: { packet: BuilderPacketStatus }) {
  const publication = packet.publication
  return (
    <div style={{ ...card, display: 'grid', gap: 8, minWidth: 0 }}>
      <span style={cardTitle}>Publication</span>
      {publication ? (
        <>
          <span style={bodyText}>{publication.merged ? 'Merged' : `Pull request #${publication.pr_number}`}</span>
          <span style={cardMeta}>checks: {displayState(publication.checks_state ?? 'unknown')}</span>
          <span style={cardMeta}>review: {displayState(publication.review_state ?? 'unknown')}</span>
          {publication.updated_at && <span style={cardMeta}>Updated <TimeValue value={publication.updated_at} /></span>}
          {publication.pr_url && (
            <>
              <a href={publication.pr_url} target="_blank" rel="noreferrer" style={{ ...bodyText, color: 'var(--primary)', overflowWrap: 'anywhere' }}>
                Open pull request #{publication.pr_number}
              </a>
              <CopyableText value={publication.pr_url} label="pr_url" />
            </>
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

function packetStatusColor(packet: BuilderPacketStatus): string {
  if (packetNeedsAttention(packet)) return 'var(--c-red)'
  if (isPacketActive(packet)) return 'var(--c-green)'
  if (packet.task_state === 'done') return 'var(--ink-2)'
  return 'var(--ink-2)'
}

function StatusLegend() {
  const items: Array<{ color: string; label: string; description: string }> = [
    { color: 'var(--c-red)', label: 'needs attention', description: 'blocked or failed — you must act' },
    { color: 'var(--c-green)', label: 'active', description: 'running right now' },
    { color: 'var(--ink-2)', label: 'queued / done', description: 'waiting or completed' },
  ]
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', padding: '6px 4px' }}>
      {items.map((item) => (
        <span
          key={item.label}
          title={item.description}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }}
        >
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
          {item.label}
        </span>
      ))}
    </div>
  )
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
    || packet.task_state === 'cancelled'
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

function newBuilderMsgId() {
  return `bmsg-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function BuilderChat() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, open])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')

    const userMsg: Message = {
      id: newBuilderMsgId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])

    const aiMsgId = newBuilderMsgId()
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, aiMsg])
    setIsStreaming(true)

    const abort = new AbortController()
    abortRef.current = abort

    const history = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    })) as Message[]

    let accumulated = ''
    try {
      for await (const chunk of streamChat('builder', history, abort.signal)) {
        if (chunk.done) break
        accumulated += chunk.content
        setMessages((prev) =>
          prev.map((m) => (m.id === aiMsgId ? { ...m, content: accumulated } : m)),
        )
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, content: '⚠ error connecting to gateway' }
            : m,
        ),
      )
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [input, isStreaming, messages])

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      style={{
        borderTop: '1px solid var(--line)',
        marginTop: 8,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.06em',
          textTransform: 'lowercase',
          color: 'var(--ink-2)',
        }}
      >
        <span>{open ? '▾' : '▸'} builder chat</span>
        {isStreaming && <span style={{ color: 'var(--c-green)' }}>● streaming</span>}
      </button>

      {open && (
        <div
          style={{
            display: 'grid',
            gridTemplateRows: '1fr auto',
            maxHeight: 320,
            overflow: 'hidden',
            borderTop: '1px solid var(--line)',
          }}
        >
          <div
            ref={listRef}
            style={{
              overflowY: 'auto',
              padding: '8px 14px',
              display: 'grid',
              gap: 8,
              alignContent: 'start',
            }}
          >
            {messages.length === 0 && (
              <p
                style={{
                  margin: 0,
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--ink-2)',
                  padding: '8px 0',
                }}
              >
                Talk to the builder while it executes.
              </p>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  padding: '6px 10px',
                  borderRadius: 6,
                  background:
                    m.role === 'user' ? 'var(--surface-2)' : 'var(--surface)',
                  border: '1px solid var(--line)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: 'var(--ink)',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {m.content || (m.role === 'assistant' ? '…' : '')}
              </div>
            ))}
          </div>

          <div
            style={{
              display: 'flex',
              gap: 6,
              padding: '6px 14px 10px',
              borderTop: '1px solid var(--line)',
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="talk to builder…"
              rows={1}
              disabled={isStreaming}
              style={{
                flex: 1,
                resize: 'none',
                border: '1px solid var(--line)',
                borderRadius: 4,
                padding: '6px 8px',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                background: 'var(--bg)',
                color: 'var(--ink)',
                outline: 'none',
                lineHeight: 1.5,
              }}
            />
            {isStreaming ? (
              <button
                type="button"
                onClick={handleStop}
                style={{
                  border: '1px solid var(--line)',
                  borderRadius: 4,
                  background: 'var(--surface)',
                  color: 'var(--c-red)',
                  cursor: 'pointer',
                  padding: '4px 10px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                }}
              >
                stop
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim()}
                style={{
                  border: '1px solid var(--line)',
                  borderRadius: 4,
                  background: 'var(--surface)',
                  color: 'var(--ink)',
                  cursor: input.trim() ? 'pointer' : 'default',
                  opacity: input.trim() ? 1 : 0.4,
                  padding: '4px 10px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                send
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function isExpired(validUntil: string | undefined): boolean {
  if (!validUntil) return false
  const timestamp = Date.parse(validUntil)
  return Number.isFinite(timestamp) && timestamp < Date.now()
}
