'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import { useProposeBuilderJob, useApproveBuilderJob, useResumeBuilderJob } from '@/lib/queries'
import type { ConversationProposal } from '@/lib/gateway'

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

interface Props {
  task: BuilderProposalTask
  chatId: string
  messageIndex: number
}

export function BuilderProposalCard({ task, chatId, messageIndex }: Props) {
  const storageKey = `kitty.builder-proposal.${chatId}.${messageIndex}`
  const propose = useProposeBuilderJob()
  const approve = useApproveBuilderJob()
  const [proposal, setProposal] = useState<ConversationProposal | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [resumedMissionId, setResumedMissionId] = useState<string | null>(null)
  const resume = useResumeBuilderJob(resumedMissionId)

  useEffect(() => {
    setResumedMissionId(window.localStorage.getItem(storageKey))
  }, [storageKey])

  if (resumedMissionId) {
    return <ResumedBuilderJob task={task} resume={resume} />
  }

  if (!task.objective || !task.instructions || !task.allowed_paths?.length) {
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
    propose.mutate(
      {
        objective: task.objective,
        instructions: task.instructions,
        allowed_paths: task.allowed_paths,
        title: task.title,
        initiative_id: task.initiative_id,
        acceptance_criteria: task.acceptance_criteria,
        validation_commands: task.validation_commands,
      },
      { onSuccess: (data) => setProposal(data) },
    )
  }

  const doApprove = () => {
    if (!proposal?.ok || !proposal.prepared_manifest || !proposal.manifest_sha256 || !proposal.expected_base_sha || !proposal.approval_nonce) {
      return
    }
    setConfirming(false)
    approve.mutate(
      {
        prepared_manifest: proposal.prepared_manifest,
        expected_manifest_sha: proposal.manifest_sha256,
        expected_base_sha: proposal.expected_base_sha,
        approval_nonce: proposal.approval_nonce,
        confirmed: true,
      },
      {
        onSuccess: (data) => {
          if (data.ok && data.mission_id) {
            window.localStorage.setItem(storageKey, data.mission_id)
            setResumedMissionId(data.mission_id)
          }
        },
      },
    )
  }

  return (
    <div style={cardStyle}>
      <div style={headerRow}>
        <span style={badgeStyle}>BUILDER PROPOSAL</span>
        <span style={titleStyle}>{task.title || task.objective}</span>
      </div>

      <p style={fieldStyle}><strong>Objective:</strong> {task.objective}</p>
      <p style={fieldStyle}><strong>Instructions:</strong> {task.instructions}</p>
      <p style={fieldStyle}><strong>Allowed paths:</strong> {task.allowed_paths.join(', ')}</p>

      {!proposal && (
        <button type="button" onClick={doPropose} disabled={propose.isPending} style={btnPrimary}>
          {propose.isPending ? 'Compiling…' : 'Compile as Builder Mission'}
        </button>
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

          {!confirming ? (
            <button type="button" onClick={() => setConfirming(true)} style={btnPrimary}>
              Approve
            </button>
          ) : (
            <div style={confirmRow}>
              <span style={{ flex: 1 }}>Create this Builder job? Nothing runs until Builder&apos;s own free worker picks it up.</span>
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

/** Rendered once a proposal has been approved — this mount or a previous
 * one. `resume` is the live `useResumeBuilderJob` query for the persisted
 * mission id; Builder's own durable state is the only source of truth here,
 * never the chat message that triggered the proposal. */
function ResumedBuilderJob({
  task,
  resume,
}: {
  task: BuilderProposalTask
  resume: ReturnType<typeof useResumeBuilderJob>
}) {
  const data = resume.data

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

      {data && !data.ok && (
        <span style={errorText}>{data.error || 'Could not find this job in Builder.'}</span>
      )}

      {data?.ok && (
        <div style={successBox}>
          <p style={fieldStyle}>
            <strong>Mission:</strong> {data.mission?.id}
            {data.mission?.state ? ` — ${data.mission.state}` : ''}
          </p>
          {data.current_work?.state && (
            <p style={fieldStyle}><strong>Current work:</strong> {data.current_work.state}</p>
          )}
          {data.blocker && (
            <p style={fieldStyle}><strong>Blocked:</strong> {data.blocker}</p>
          )}
          {data.pr?.url && (
            <p style={fieldStyle}>
              <strong>PR:</strong> <a href={data.pr.url} target="_blank" rel="noreferrer">{data.pr.url}</a>
              {data.pr.checks_state ? ` — checks: ${data.pr.checks_state}` : ''}
            </p>
          )}
          <p style={fieldStyle}>
            Track it in the Work view — Kitty&apos;s chat does not run or report on it directly.
          </p>
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
