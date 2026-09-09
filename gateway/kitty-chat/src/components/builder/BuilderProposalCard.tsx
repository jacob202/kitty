'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { useProposeBuilderJob, useApproveBuilderJob, useResumeBuilderJob, useMission } from '@/lib/queries'
import type { ConversationApproveRequest, ConversationProposal } from '@/lib/gateway'

/**
 * Renders a conversation-compiled coding task as a structured proposal and
 * requires an explicit Approve click before any durable Builder job is
 * created. Kitty's chat never executes code or creates the job itself —
 * this only calls the same propose/approve contract the KittyBuilder MCP
 * bridge already exposes to external clients (gateway/conversation_handoff.py).
 *
 * `task` is parsed from a ```kitty-builder-proposal fenced block in an
 * assistant message; see ChatMessage.tsx's CodeBlock renderer.
 *
 * The fenced block itself never changes once Kitty writes it, so once a job
 * is approved this component persists the resulting mission id to
 * localStorage under `chatId`+`messageIndex`. On a later mount (page
 * reload, reopened chat) it finds that id and shows the job's current
 * durable state via `resume` instead of resetting to a blank "Compile"
 * button — chat history is never the source of truth for whether the job
 * exists.
 */
export interface BuilderProposalTask {
  objective: string
  instructions: string
  allowed_paths: string[]
  title?: string
  initiative_id?: string
  acceptance_criteria?: string[]
  validation_commands?: string[]
}

// Some browsers (privacy mode, blocked site data, sandboxed embeds) throw on
// any localStorage access. Durable Builder state never depends on it — it is
// only a reload convenience — so a storage failure must not stop the user from
// reviewing or approving a freshly compiled proposal.
const safeStorage = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string): void {
    try {
      window.localStorage.setItem(key, value)
    } catch {
      /* storage unavailable — reload recovery is best-effort only */
    }
  },
  remove(key: string): void {
    try {
      window.localStorage.removeItem(key)
    } catch {
      /* storage unavailable — nothing to clean up */
    }
  },
}

// gateway.ts's describeFetchError already turns an HTTP error status into
// "Gateway returned <status> <statusText>", but when the browser can't reach
// the gateway at all (connection refused, DNS failure), fetch() itself
// throws with the browser's own message — Chromium's is the literal string
// "Failed to fetch", which is not something a non-technical user can act on.
function friendlyMutationError(err: unknown, fallback: string): string {
  if (!(err instanceof Error)) return fallback
  const message = err.message
  if (!message || /failed to fetch|networkerror|load failed/i.test(message)) {
    return 'Could not reach the Kitty gateway — check that it is running, then try again.'
  }
  return message
}

interface PendingApprovalCheckpoint {
  version: 1
  state: 'pending'
  missionId: string
  approval: ConversationApproveRequest
  task?: BuilderProposalTask
}

interface ProposalIdentityCheckpoint {
  version: 2
  state: 'proposal'
  initiativeId: string
  task: BuilderProposalTask
}

interface PreparedProposalCheckpoint {
  version: 3
  state: 'prepared'
  initiativeId: string
  gatewayMissionId: string
  task: BuilderProposalTask
  proposal: ConversationProposal
}

function isBuilderProposalTask(value: unknown): value is BuilderProposalTask {
  if (!value || typeof value !== 'object') return false
  const task = value as Partial<BuilderProposalTask>
  return typeof task.objective === 'string'
    && typeof task.instructions === 'string'
    && Array.isArray(task.allowed_paths)
    && task.allowed_paths.every(path => typeof path === 'string')
}

function readStoredApproval(raw: string | null): {
  missionId: string | null
  pending: ConversationApproveRequest | null
  task: BuilderProposalTask | null
  initiativeId: string | null
  proposal: ConversationProposal | null
} | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<PendingApprovalCheckpoint> | null
    if (
      parsed
      && typeof parsed === 'object'
      && parsed.version === 1
      && parsed.state === 'pending'
      && typeof parsed.missionId === 'string'
      && parsed.missionId
      && parsed.approval
      && typeof parsed.approval === 'object'
    ) {
      return {
        missionId: parsed.missionId,
        pending: parsed.approval as ConversationApproveRequest,
        task: isBuilderProposalTask(parsed.task) ? parsed.task : null,
        initiativeId: null,
        proposal: null,
      }
    }
    const prepared = parsed as Partial<PreparedProposalCheckpoint> | null
    if (
      prepared
      && typeof prepared === 'object'
      && prepared.version === 3
      && prepared.state === 'prepared'
      && typeof prepared.initiativeId === 'string'
      && prepared.initiativeId
      && typeof prepared.gatewayMissionId === 'string'
      && prepared.gatewayMissionId
      && isBuilderProposalTask(prepared.task)
      && prepared.proposal
      && typeof prepared.proposal === 'object'
      && prepared.proposal.ok === true
      && prepared.proposal.mission_id === prepared.initiativeId
      && prepared.proposal.gateway_mission_id === prepared.gatewayMissionId
    ) {
      return {
        missionId: null,
        pending: null,
        task: prepared.task,
        initiativeId: prepared.initiativeId,
        proposal: prepared.proposal as ConversationProposal,
      }
    }
    const proposal = parsed as Partial<ProposalIdentityCheckpoint> | null
    if (
      proposal
      && typeof proposal === 'object'
      && proposal.version === 2
      && proposal.state === 'proposal'
      && typeof proposal.initiativeId === 'string'
      && proposal.initiativeId
      && isBuilderProposalTask(proposal.task)
    ) {
      return {
        missionId: null,
        pending: null,
        task: proposal.task,
        initiativeId: proposal.initiativeId,
        proposal: null,
      }
    }
  } catch {
    // Legacy approved entries are plain mission ids, not JSON.
  }
  return { missionId: raw, pending: null, task: null, initiativeId: null, proposal: null }
}

export function readPendingBuilderProposalTask(raw: string | null): BuilderProposalTask | null {
  return readStoredApproval(raw)?.task ?? null
}

function proposalIdentityValue(initiativeId: string, task: BuilderProposalTask): string {
  return JSON.stringify({ version: 2, state: 'proposal', initiativeId, task } satisfies ProposalIdentityCheckpoint)
}

function preparedProposalValue(proposal: ConversationProposal, task: BuilderProposalTask): string | null {
  const initiativeId = proposal.mission_id
  const gatewayMissionId = proposal.gateway_mission_id
  if (!proposal.ok || !initiativeId || !gatewayMissionId) return null
  return JSON.stringify({
    version: 3,
    state: 'prepared',
    initiativeId,
    gatewayMissionId,
    task,
    proposal,
  } satisfies PreparedProposalCheckpoint)
}

function createProposalInitiativeId(): string {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') {
    return `conv-ui-${cryptoApi.randomUUID().replace(/-/g, '')}`
  }
  const bytes = new Uint8Array(16)
  cryptoApi.getRandomValues(bytes)
  return `conv-ui-${Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')}`
}

function pendingApprovalValue(missionId: string, approval: ConversationApproveRequest, task: BuilderProposalTask): string {
  return JSON.stringify({ version: 1, state: 'pending', missionId, approval, task } satisfies PendingApprovalCheckpoint)
}

interface Props {
  task: BuilderProposalTask
  chatId: string
  messageIndex: number
  /**
   * Switches the top-level view to the Work tab. Chat never runs or reports on
   * the job itself — once a proposal is approved, this is the seam that hands
   * the durable Builder mission to the Work view for progress and recovery.
   * Optional so the card still renders in hosts without the navigation
   * surface (static previews, isolated tests).
   */
  onOpenWork?: () => void
  /** Override the per-chat-message key for hosts such as Work that only need
   * one pending approval checkpoint at a time. */
  recoveryStorageKey?: string
  /** Chat keeps approved mission ids beside durable messages. Work already
   * projects durable Builder state, so it persists only ambiguous approvals. */
  persistResolvedMission?: boolean
}

export function BuilderProposalCard({
  task,
  chatId,
  messageIndex,
  onOpenWork,
  recoveryStorageKey,
  persistResolvedMission = true,
}: Props) {
  const storageKey = recoveryStorageKey ?? `kitty.builder-proposal.${chatId}.${messageIndex}`
  const propose = useProposeBuilderJob()
  const approve = useApproveBuilderJob()
  const [draft, setDraft] = useState<BuilderProposalTask>(task)
  const [editing, setEditing] = useState(false)
  const [proposal, setProposal] = useState<ConversationProposal | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [resumedMissionId, setResumedMissionId] = useState<string | null>(null)
  const [pendingApproval, setPendingApproval] = useState<ConversationApproveRequest | null>(null)
  const [proposalIdentity, setProposalIdentity] = useState<string | null>(null)
  const resume = useResumeBuilderJob(resumedMissionId)
  const gatewayMissionId = proposal?.gateway_mission_id
    || pendingApproval?.gateway_mission_id
    || (resumedMissionId ? `gateway-conversation:${resumedMissionId}` : null)
  const mission = useMission(gatewayMissionId)

  useEffect(() => {
    const stored = readStoredApproval(safeStorage.get(storageKey))
    setResumedMissionId(stored?.missionId ?? null)
    setPendingApproval(stored?.pending ?? null)
    setProposalIdentity(stored?.initiativeId ?? null)
    setProposal(stored?.proposal ?? null)
  }, [storageKey])

  useEffect(() => {
    if (pendingApproval && resumedMissionId && resume.data?.mission?.id === resumedMissionId) {
      if (persistResolvedMission) safeStorage.set(storageKey, resumedMissionId)
      else safeStorage.remove(storageKey)
      setPendingApproval(null)
    }
  }, [pendingApproval, persistResolvedMission, resume.data?.mission?.id, resumedMissionId, storageKey])

  const retryPendingApproval = () => {
    if (!pendingApproval || !resumedMissionId) return
    approve.mutate(pendingApproval, {
      onSuccess: (data) => {
        if (data.ok && data.mission_id) {
          if (persistResolvedMission) safeStorage.set(storageKey, data.mission_id)
          else safeStorage.remove(storageKey)
          setPendingApproval(null)
          setResumedMissionId(data.mission_id)
        } else {
          safeStorage.remove(storageKey)
          setPendingApproval(null)
          setResumedMissionId(null)
        }
      },
    })
  }

  if (resumedMissionId) {
    if (pendingApproval && resume.data?.error_code === 'work_not_found') {
      return (
        <PendingApprovalRecovery
          task={draft}
          missionId={resumedMissionId}
          approve={approve}
          onRetry={retryPendingApproval}
        />
      )
    }
    return <ResumedBuilderJob task={draft} resume={resume} onOpenWork={onOpenWork} />
  }

  if (!draft.objective || !draft.instructions || !draft.allowed_paths?.length) {
    return (
      <div style={cardStyle}>
        <span style={errorText}>
          Malformed Builder proposal: objective, instructions, and at least one allowed path are required.
        </span>
      </div>
    )
  }

  const doPropose = () => {
    setProposal(null)
    const initiativeId = draft.initiative_id || proposalIdentity || createProposalInitiativeId()
    if (!draft.initiative_id && proposalIdentity !== initiativeId) {
      safeStorage.set(storageKey, proposalIdentityValue(initiativeId, draft))
      setProposalIdentity(initiativeId)
    }
    propose.mutate(
      {
        objective: draft.objective,
        instructions: draft.instructions,
        allowed_paths: draft.allowed_paths,
        title: draft.title,
        initiative_id: initiativeId,
        acceptance_criteria: draft.acceptance_criteria,
        validation_commands: draft.validation_commands,
      },
      {
        onSuccess: (data) => {
          setProposal(data)
          const checkpoint = preparedProposalValue(data, draft)
          if (checkpoint) {
            safeStorage.set(storageKey, checkpoint)
            setProposalIdentity(data.mission_id ?? initiativeId)
          }
        },
      },
    )
  }

  const doApprove = () => {
    if (!proposal?.ok || !proposal.prepared_manifest || !proposal.manifest_sha256 || !proposal.expected_base_sha || !proposal.approval_nonce) {
      return
    }
    setConfirming(false)
    const missionId = proposal.mission_id
    if (!missionId) return
    const approvalPayload: ConversationApproveRequest = {
      prepared_manifest: proposal.prepared_manifest,
      expected_manifest_sha: proposal.manifest_sha256,
      expected_base_sha: proposal.expected_base_sha,
      approval_nonce: proposal.approval_nonce,
      gateway_mission_id: proposal.gateway_mission_id || undefined,
      confirmed: true,
    }
    // Persist the exact immutable approval before the external effect. If the
    // durable Builder write succeeds but the HTTP receipt is lost, reload can
    // reconcile by mission id and safely replay this same idempotent approval
    // instead of compiling a second initiative.
    safeStorage.set(storageKey, pendingApprovalValue(missionId, approvalPayload, draft))
    setPendingApproval(approvalPayload)
    approve.mutate(
      approvalPayload,
      {
        onSuccess: (data) => {
          if (data.ok && data.mission_id) {
            if (persistResolvedMission) safeStorage.set(storageKey, data.mission_id)
            else safeStorage.remove(storageKey)
            setPendingApproval(null)
            setResumedMissionId(data.mission_id)
          } else if (data.state === 'recovery_required' && data.error_code === 'mission_binding_failed') {
            // Builder may already have accepted the exact job. Keep the immutable
            // approval checkpoint so the same nonce-bound request can reconcile
            // Mission's locator without compiling or approving a second job.
          } else {
            // A server receipt with ok:false is a definite refusal, not an
            // ambiguous lost response. Preserve the visible proposal so the
            // user can correct/re-prepare it rather than pinning a fake job.
            safeStorage.remove(storageKey)
            setPendingApproval(null)
          }
        },
        onError: () => {
          // The effect may have committed even though its response was lost.
          // Switch to reconciliation instead of offering a fresh compile.
          setResumedMissionId(missionId)
        },
      },
    )
  }

  return (
    <div style={cardStyle}>
      <div style={headerRow}>
        <span style={badgeStyle}>BUILDER PROPOSAL</span>
        <span style={titleStyle}>{draft.title || draft.objective}</span>
      </div>

      {editing ? (
        <div style={{ display: 'grid', gap: 8 }}>
          <label style={editLabelStyle}>
            Objective
            <input
              aria-label="Proposal objective"
              value={draft.objective}
              onChange={(event) => setDraft(current => ({ ...current, objective: event.target.value }))}
              style={editInputStyle}
            />
          </label>
          <label style={editLabelStyle}>
            Instructions
            <textarea
              aria-label="Proposal instructions"
              value={draft.instructions}
              onChange={(event) => setDraft(current => ({ ...current, instructions: event.target.value }))}
              rows={4}
              style={editInputStyle}
            />
          </label>
          <label style={editLabelStyle}>
            Allowed paths — one per line
            <textarea
              aria-label="Proposal allowed paths"
              value={draft.allowed_paths.join('\n')}
              onChange={(event) => setDraft(current => ({
                ...current,
                allowed_paths: event.target.value.split(/\r?\n/).map(path => path.trim()).filter(Boolean),
              }))}
              rows={3}
              style={editInputStyle}
            />
          </label>
          <button
            type="button"
            aria-label="Save proposal changes"
            onClick={() => setEditing(false)}
            disabled={!draft.objective.trim() || !draft.instructions.trim() || draft.allowed_paths.length === 0}
            style={btnBase}
          >
            Save changes
          </button>
        </div>
      ) : (
        <>
          <p style={fieldStyle}><strong>Objective:</strong> {draft.objective}</p>
          <p style={fieldStyle}><strong>Instructions:</strong> {draft.instructions}</p>
          <p style={fieldStyle}><strong>Allowed paths:</strong> {draft.allowed_paths.join(', ')}</p>
        </>
      )}

      {!proposal && !editing && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={doPropose} disabled={propose.isPending} style={btnPrimary}>
            {propose.isPending ? 'Compiling…' : 'Compile as Builder Mission'}
          </button>
          <button type="button" aria-label="Edit proposal" onClick={() => setEditing(true)} style={btnBase}>
            Edit proposal
          </button>
        </div>
      )}

      {propose.isError && (
        <span style={errorText}>{friendlyMutationError(propose.error, 'Could not compile the proposal.')}</span>
      )}

      {proposal && !proposal.ok && (
        <span style={errorText}>{proposal.error || 'proposal was refused'}</span>
      )}

      {proposal?.ok && (
        <div style={preparedBox}>
          <p style={fieldStyle}><strong>Mission ID:</strong> {proposal.mission_id}</p>
          {gatewayMissionId && (
            <p style={fieldStyle}>
              <strong>Mission state:</strong> {mission.data?.status ?? proposal.gateway_mission_status ?? 'loading'}
            </p>
          )}
          <p style={fieldStyle}><strong>Acceptance criteria:</strong></p>
          <ul style={ulStyle}>
            {((proposal.prepared_manifest?.packets as Array<Record<string, unknown>> | undefined)?.[0]
              ?.acceptance_criteria as string[] | undefined ?? []
            ).map((c) => <li key={c}>{c}</li>)}
          </ul>
          {proposal.warnings && proposal.warnings.length > 0 && (
            <div style={warningBox}>
              {proposal.warnings.map((w) => <div key={w}>⚠ {w}</div>)}
            </div>
          )}
          <p style={fieldStyle}>
            <strong>Design:</strong> {proposal.design?.path}<br />
            <strong>Plan:</strong> {proposal.plan?.path}
          </p>

          {proposal.gateway_mission_id && (mission.data?.plan.review_state ?? proposal.gateway_plan_review_state) !== 'approved' ? (
            <div style={warningBox}>
              <div>
                {(mission.data?.plan.review_state ?? proposal.gateway_plan_review_state) === 'rejected'
                  ? 'Independent plan review rejected this version. Revise the proposal before Builder execution.'
                  : 'Independent plan review pending. Kitty started a separate read-only reviewer; Builder execution remains locked until it approves this exact plan.'}
              </div>
              {mission.isError && <div>Mission status is temporarily unavailable. The review gate remains locked.</div>}
              <button type="button" onClick={doPropose} disabled={propose.isPending} style={btnBase}>
                {propose.isPending ? 'Retrying…' : 'Retry review'}
              </button>
            </div>
          ) : !confirming ? (
            <button type="button" onClick={() => setConfirming(true)} style={btnPrimary}>
              Approve
            </button>
          ) : (
            <div style={confirmRow}>
              <span style={{ flex: 1 }}>Create this Builder job? Builder will choose the execution route under current policy; any spend remains subject to Builder&apos;s authorization gates.</span>
              <button type="button" onClick={doApprove} disabled={approve.isPending} style={btnConfirm}>
                {approve.isPending ? '…' : 'Confirm'}
              </button>
              <button type="button" onClick={() => setConfirming(false)} style={btnBase}>
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {approve.isError && (
        <span style={errorText}>{friendlyMutationError(approve.error, 'Could not create the Builder job.')}</span>
      )}
      {approve.data && !approve.data.ok && (
        <span style={errorText}>{approve.data.error || 'approval was refused'}</span>
      )}
    </div>
  )
}

function PendingApprovalRecovery({
  task,
  missionId,
  approve,
  onRetry,
}: {
  task: BuilderProposalTask
  missionId: string
  approve: ReturnType<typeof useApproveBuilderJob>
  onRetry: () => void
}) {
  return (
    <div style={cardStyle}>
      <div style={headerRow}>
        <span style={badgeStyle}>BUILDER APPROVAL</span>
        <span style={titleStyle}>{task.title || task.objective}</span>
      </div>
      <div style={warningBox}>
        Kitty could not confirm whether the approval receipt arrived. Builder has no durable job for {missionId} yet.
        Retry the same approved version to reconcile it safely; Kitty will not compile a second job.
      </div>
      {approve.isError && (
        <span style={errorText}>{friendlyMutationError(approve.error, 'Could not reconcile the Builder approval.')}</span>
      )}
      <button type="button" onClick={onRetry} disabled={approve.isPending} style={btnConfirm}>
        {approve.isPending ? 'Reconciling…' : 'Retry same approval'}
      </button>
    </div>
  )
}

/** Rendered once a proposal has been approved — this mount or a previous
 * one. `resume` is the live `useResumeBuilderJob` query for the persisted
 * mission id; Builder's own durable state is the only source of truth here,
 * never the chat message that triggered the proposal. */
function ResumedBuilderJob({
  task,
  resume,
  onOpenWork,
}: {
  task: BuilderProposalTask
  resume: ReturnType<typeof useResumeBuilderJob>
  onOpenWork?: () => void
}) {
  const data = resume.data
  // resume_context()'s `ok` reflects Kitty's own cold-start health check, not
  // whether the job was found — durable Builder facts (mission/current_work/
  // blocker/pr) are populated whenever the mission is found, even when `ok`
  // is false for an unrelated reason. Gate on the mission id, not on `ok`, so
  // a cold-start hiccup never hides real job status behind a raw error.
  const found = Boolean(data?.mission?.id)

  return (
    <div style={cardStyle}>
      <div style={headerRow}>
        <span style={badgeStyle}>BUILDER JOB</span>
        <span style={titleStyle}>{task.title || task.objective}</span>
      </div>

      {resume.isLoading && <span style={fieldStyle}>Checking current status…</span>}

      {resume.isError && (
        <span style={errorText}>
          {friendlyMutationError(resume.error, 'Could not check the job’s current status.')}
        </span>
      )}

      {data && !found && (
        <span style={errorText}>{data.error || 'Could not find this job in Builder.'}</span>
      )}

      {found && (
        <div
          style={data!.awaiting_acceptance ? attentionBox : successBox}
          data-testid={data!.awaiting_acceptance ? 'builder-job-awaiting-acceptance' : 'builder-job-status'}
        >
          <p style={fieldStyle}>
            <strong>Mission:</strong> {data!.mission?.id}
            {data!.mission?.state ? ` — ${data!.mission.state}` : ''}
          </p>
          {data!.current_work?.state && (
            <p style={fieldStyle}><strong>Current work:</strong> {data!.current_work.state}</p>
          )}
          {/* Builder finishing its task is not the same statement as the
              outcome being accepted. Showing only the first is how a job that
              nobody has signed off reads as finished. */}
          {data!.awaiting_acceptance && (
            <p style={fieldStyle}>
              <strong>Built, not accepted yet:</strong>{' '}
              {data!.mission_acceptance?.state === 'unavailable'
                ? `Kitty could not check whether this outcome was accepted${
                    data!.mission_acceptance.error
                      ? `: ${data!.mission_acceptance.error}`
                      : '.'
                  } Check Kitty status and Mission storage, then retry.`
                : 'Builder finished this work. Nobody has accepted the result yet.'}
            </p>
          )}
          {data!.blocker && (
            <p style={fieldStyle}><strong>Blocked:</strong> {data!.blocker}</p>
          )}
          {data!.pr?.url && (
            <p style={fieldStyle}>
              <strong>PR:</strong> <a href={data!.pr.url} target="_blank" rel="noreferrer">{data!.pr.url}</a>
              {data!.pr.checks_state ? ` — checks: ${data!.pr.checks_state}` : ''}
            </p>
          )}
          <p style={fieldStyle}>
            Track it in the Work view — Kitty&apos;s chat does not run or report on it directly.
          </p>
          {onOpenWork && (
            <button
              type="button"
              onClick={onOpenWork}
              style={btnOpenWork}
              aria-label="Open this Builder job in the Work view"
              data-testid="builder-proposal-open-work"
            >
              <ArrowUpRight size={11} />
              <span>Open in Work</span>
            </button>
          )}
        </div>
      )}

      {data && !data.ok && found && (
        <div style={warningBox}>
          Kitty&apos;s own status check needs attention, so this may be stale: {data.error || 'unknown issue'}
        </div>
      )}
    </div>
  )
}

const cardStyle: CSSProperties = {
  border: '1.5px solid var(--line)',
  borderRadius: 12,
  padding: '12px 14px',
  margin: '8px 0',
  background: 'var(--surface-2)',
  fontFamily: 'var(--font-body)',
  fontSize: 12.5,
  color: 'var(--ink)',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  maxWidth: 480,
}

const headerRow: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8 }

const badgeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.05em',
  color: 'var(--ink-3)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '2px 6px',
}

const titleStyle: CSSProperties = { fontWeight: 600 }

const fieldStyle: CSSProperties = { margin: 0, lineHeight: 1.5 }

const editLabelStyle: CSSProperties = { display: 'grid', gap: 4, fontSize: 11, color: 'var(--ink-2)' }
const editInputStyle: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  border: '1px solid var(--line)',
  borderRadius: 6,
  background: 'var(--surface-1)',
  color: 'var(--ink)',
  padding: '7px 8px',
  fontFamily: 'var(--font-body)',
  fontSize: 12,
}

const ulStyle: CSSProperties = { margin: '2px 0', paddingLeft: 18 }

const preparedBox: CSSProperties = {
  borderTop: '1px solid var(--line)',
  paddingTop: 8,
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

const warningBox: CSSProperties = { color: '#FF9800', fontSize: 11 }

const errorText: CSSProperties = { color: '#F44336', fontSize: 11 }

const successBox: CSSProperties = {
  background: '#4CAF5011',
  border: '1px solid #4CAF50',
  borderRadius: 8,
  padding: 8,
  color: '#2e7d32',
}

const attentionBox: CSSProperties = {
  background: '#FF980011',
  border: '1px solid #FF9800',
  borderRadius: 8,
  padding: 8,
  color: '#B45309',
}

const btnBase: CSSProperties = {
  background: 'none',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '4px 10px',
  cursor: 'pointer',
  color: 'var(--ink)',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
}

const btnPrimary: CSSProperties = {
  ...btnBase,
  background: 'var(--primary)',
  color: 'var(--on-primary)',
  borderColor: 'var(--primary)',
  alignSelf: 'flex-start',
}

const btnConfirm: CSSProperties = {
  ...btnBase,
  background: '#4CAF50',
  color: '#fff',
  borderColor: '#4CAF50',
}

const confirmRow: CSSProperties = { display: 'flex', alignItems: 'center', gap: 6 }

const btnOpenWork: CSSProperties = {
  ...btnBase,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  alignSelf: 'flex-start',
  marginTop: 2,
}
