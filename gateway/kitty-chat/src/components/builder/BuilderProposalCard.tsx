'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import { useProposeBuilderJob, useApproveBuilderJob, useResumeBuilderJob } from '@/lib/queries'
import { useBuilderAction, useSupervisor, type BuilderCommand } from '@/lib/work'
import type { ConversationProposal, ConversationResume } from '@/lib/gateway'

export interface BuilderProposalTask {
  objective: string
  instructions: string
  allowed_paths: string[]
  title?: string
  initiative_id?: string
  acceptance_criteria?: string[]
  validation_commands?: string[]
}

interface Props {
  task: BuilderProposalTask
  chatId: string
  messageIndex: number
}

const MAX_SUMMARY_LENGTH = 280

/** A chat fence is a proposal only. Durable Builder work starts at the
 * explicit send action, and the returned mission id is retained privately for
 * reload recovery. */
export function BuilderProposalCard({ task, chatId, messageIndex }: Props) {
  const storageKey = `kitty.builder-proposal.${chatId}.${messageIndex}`
  const propose = useProposeBuilderJob()
  const approve = useApproveBuilderJob()
  const supervisor = useSupervisor()
  const [proposal, setProposal] = useState<ConversationProposal | null>(null)
  const [resumedMissionId, setResumedMissionId] = useState<string | null>(null)
  const [proposalError, setProposalError] = useState(false)
  const [approvalError, setApprovalError] = useState(false)
  const [approvalSent, setApprovalSent] = useState(false)
  const resume = useResumeBuilderJob(resumedMissionId)

  useEffect(() => {
    setResumedMissionId(window.localStorage.getItem(storageKey))
  }, [storageKey])

  if (resumedMissionId) {
    return (
      <ResumedBuilderJob
        task={task}
        missionId={resumedMissionId}
        resume={resume}
        supervisor={supervisor}
      />
    )
  }

  if (!task.objective || !task.instructions || !task.allowed_paths?.length) {
    return (
      <div style={cardStyle}>
        <span style={errorText}>Could not prepare this work proposal. Ask Kitty to prepare it again.</span>
      </div>
    )
  }

  const doPropose = () => {
    setProposal(null)
    setProposalError(false)
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
      {
        onSuccess: data => {
          if (data.ok) setProposal(data)
          else setProposalError(true)
        },
        onError: () => setProposalError(true),
      },
    )
  }

  const doApprove = (retry = false) => {
    if ((!retry && approvalSent) || !proposal?.ok || !proposal.prepared_manifest || !proposal.manifest_sha256 || !proposal.expected_base_sha || !proposal.approval_nonce) return
    setApprovalSent(true)
    setApprovalError(false)
    approve.mutate(
      {
        prepared_manifest: proposal.prepared_manifest,
        expected_manifest_sha: proposal.manifest_sha256,
        expected_base_sha: proposal.expected_base_sha,
        approval_nonce: proposal.approval_nonce,
        confirmed: true,
      },
      {
        onSuccess: data => {
          if (data.mission_id) {
            window.localStorage.setItem(storageKey, data.mission_id)
            setResumedMissionId(data.mission_id)
          }
          if (!data.ok || !data.mission_id) {
            setApprovalError(true)
          }
        },
        onError: () => setApprovalError(true),
      },
    )
  }

  const criteria = task.acceptance_criteria?.length
    ? task.acceptance_criteria
    : ((proposal?.prepared_manifest?.packets as Array<Record<string, unknown>> | undefined)?.[0]
      ?.acceptance_criteria as string[] | undefined ?? [])

  return (
    <div style={cardStyle}>
      <div style={headerRow}>
        <span style={badgeStyle}>WORK PROPOSAL</span>
        <span style={titleStyle}>{task.title || task.objective}</span>
      </div>

      <p style={fieldStyle}><strong>Outcome:</strong> {task.objective}</p>
      <p style={fieldStyle}><strong>Approach:</strong> {task.instructions}</p>
      <div style={fieldStyle}>
        <strong>Checks:</strong>
        {criteria.length > 0 ? (
          <ul style={ulStyle}>{criteria.map(check => <li key={check}>{check}</li>)}</ul>
        ) : <span> Kitty will report whether the work was validated.</span>}
      </div>

      {!proposal && (
        <button type="button" onClick={doPropose} disabled={propose.isPending} style={btnPrimary}>
          {propose.isPending ? 'Preparing…' : 'Prepare this work'}
        </button>
      )}

      {(proposalError || propose.isError) && (
        <div style={recoveryRow}>
          <span role="status" style={errorText}>Could not prepare this work.</span>
          <button type="button" onClick={doPropose} disabled={propose.isPending} style={btnBase}>Try preparing again</button>
        </div>
      )}

      {proposal?.ok && (
        <div style={preparedBox}>
          <p style={fieldStyle}>The proposal is ready. Send it when you want Builder to start the work.</p>
          <button type="button" onClick={() => doApprove()} disabled={approve.isPending || approvalSent} style={btnPrimary}>
            {approve.isPending ? 'Sending…' : 'Send this work to Builder'}
          </button>
          {approvalError && (
            <div style={recoveryRow}>
              <span role="status" style={errorText}>Could not send this work.</span>
              <button type="button" onClick={() => doApprove(true)} disabled={approve.isPending} style={btnBase}>Try sending again</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ResumedBuilderJob({
  task,
  missionId,
  resume,
  supervisor,
}: {
  task: BuilderProposalTask
  missionId: string
  resume: ReturnType<typeof useResumeBuilderJob>
  supervisor: ReturnType<typeof useSupervisor>
}) {
  const builderAction = useBuilderAction()
  const [commandError, setCommandError] = useState(false)
  const [retryCommand, setRetryCommand] = useState<BuilderCommand | 'tick' | null>(null)
  const data = resume.data
  const found = Boolean(data?.mission?.id)
  const status = jobStatus(data)
  const taskId = data?.current_work?.task_id || undefined
  const command = commandFor(status, missionId, taskId, supervisor.data)
  const terminal = status === 'completed' || status === 'cancelled'

  const runCommand = (nextCommand: BuilderCommand | 'tick') => {
    setRetryCommand(nextCommand)
    setCommandError(false)
    builderAction.mutate(nextCommand, {
      onSuccess: result => {
        if (result.ok) {
          setRetryCommand(null)
          void resume.refetch()
        } else {
          setCommandError(true)
        }
      },
      onError: () => setCommandError(true),
    })
  }

  const refresh = () => {
    setCommandError(false)
    void resume.refetch()
    void supervisor.refetch?.()
  }

  return (
    <div style={cardStyle}>
      <div style={headerRow}>
        <span style={badgeStyle}>WORK UPDATE</span>
        <span style={titleStyle}>{task.title || task.objective}</span>
      </div>

      {resume.isLoading && <span style={fieldStyle}>Checking the latest update…</span>}

      {(resume.isError || (data && !found)) && (
        <div style={recoveryRow}>
          <span role="status" style={errorText}>Could not refresh this work.</span>
          <button type="button" onClick={refresh} disabled={resume.isFetching} style={btnBase}>Refresh status</button>
        </div>
      )}

      {found && (
        <>
          <div style={statusBox}>
            <p style={fieldStyle}><strong>Status:</strong> {statusLabel(status)}</p>
            {status === 'blocked' && <p style={fieldStyle}>Builder is blocked until this work can safely continue.</p>}
            {status === 'failed' && <p style={fieldStyle}>The last attempt did not finish. You can try it again.</p>}
            {status === 'queued' && <p style={fieldStyle}>Builder will pick this up when it runs.</p>}
            {status === 'waiting_review' && <p style={fieldStyle}>The work is ready for review before it can move on.</p>}
            {status === 'cancelled' && <p style={fieldStyle}>This work was cancelled and will stay stopped.</p>}
            {status === 'completed' && <CompletedEvidence evidence={data?.evidence} />}
            {data?.evidence && <EvidenceState evidence={data.evidence} />}
          </div>

          {!terminal && !commandError && (command || taskId) && (
            <div style={actionRow}>
              {command && <button type="button" onClick={() => runCommand(command)} disabled={builderAction.isPending} style={btnPrimary}>
                {builderAction.isPending ? 'Updating…' : commandLabel(command)}
              </button>}
              {taskId && <button type="button" onClick={() => runCommand({ action: 'cancel', task_id: taskId, reason: 'Cancelled from chat' })} disabled={builderAction.isPending} style={btnBase}>Cancel this work</button>}
            </div>
          )}
          {commandError && retryCommand && (
            <div style={recoveryRow}>
              <span role="status" style={errorText}>Could not update this work.</span>
              <button type="button" onClick={() => runCommand(retryCommand)} disabled={builderAction.isPending} style={btnBase}>Try again</button>
            </div>
          )}

          <button type="button" onClick={refresh} disabled={resume.isFetching} style={refreshButton}>Refresh status</button>
        </>
      )}
    </div>
  )
}

type JobStatus = 'queued' | 'running' | 'blocked' | 'failed' | 'waiting_review' | 'cancelled' | 'completed' | 'paused' | 'unknown'

function jobStatus(data: ConversationResume | undefined): JobStatus {
  const raw = String(data?.current_work?.state || data?.mission?.state || '').toLowerCase()
  if (raw === 'queued' || raw === 'ready' || raw === 'pending') return 'queued'
  if (raw === 'claimed' || raw === 'running' || raw === 'active' || raw === 'in_progress') return 'running'
  if (raw === 'paused' || raw === 'on_hold') return 'paused'
  if (raw === 'blocked') return 'blocked'
  if (raw === 'failed' || raw === 'exhausted' || raw === 'error') return 'failed'
  if (raw === 'awaiting_review' || raw === 'pr_opened' || raw === 'review' || raw === 'review-ready') return 'waiting_review'
  if (raw === 'cancelled' || raw === 'canceled') return 'cancelled'
  if (raw === 'done' || raw === 'completed' || raw === 'succeeded' || raw === 'success') return 'completed'
  return 'unknown'
}

function statusLabel(status: JobStatus): string {
  return {
    queued: 'Queued', running: 'In progress', blocked: 'Blocked', failed: 'Failed',
    waiting_review: 'Waiting for review', cancelled: 'Cancelled', completed: 'Completed',
    paused: 'Paused', unknown: 'Status needs checking',
  }[status]
}

function commandFor(status: JobStatus, initiativeId: string, taskId: string | undefined, supervisor: { running?: boolean; eligible_now?: number } | undefined): BuilderCommand | 'tick' | null {
  if (status === 'queued' && supervisor && !supervisor.running && (supervisor.eligible_now ?? 0) > 0) return 'tick'
  if ((status === 'failed' || status === 'blocked') && taskId) return { action: 'requeue', task_id: taskId, reason: 'Retried from chat' }
  if (status === 'paused') return { action: 'resume', initiative_id: initiativeId }
  return null
}

function commandLabel(command: BuilderCommand | 'tick'): string {
  if (command === 'tick') return 'Start this work'
  if (command.action === 'requeue') return 'Try again'
  if (command.action === 'resume') return 'Resume this work'
  return 'Update this work'
}

function safeSummary(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null
  return value.trim().slice(0, MAX_SUMMARY_LENGTH)
}

function CompletedEvidence({ evidence }: { evidence: ConversationResume['evidence'] }) {
  const summary = safeSummary(evidence?.implementation?.summary)
  return summary ? <p style={fieldStyle}><strong>Result:</strong> {summary}</p> : <p style={fieldStyle}>The work completed. No short result summary was recorded.</p>
}

function EvidenceState({ evidence }: { evidence: ConversationResume['evidence'] }) {
  const validation = evidence?.validation?.status?.toLowerCase()
  const review = evidence?.review?.verdict?.toLowerCase()
  return (
    <div style={evidenceStyle}>
      {validation && <span>{validation === 'passed' || validation === 'success' ? 'Validation passed.' : validation === 'failed' ? 'Validation found an issue.' : 'Validation is pending.'}</span>}
      {review && <span>{review === 'approved' || review === 'approve' ? 'Review complete.' : review === 'reject' || review === 'request_changes' ? 'Changes were requested in review.' : 'Review is pending.'}</span>}
    </div>
  )
}

const cardStyle: CSSProperties = {
  border: '1.5px solid var(--line)', borderRadius: 12, padding: '12px 14px', margin: '8px 0',
  background: 'var(--surface-2)', fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--ink)',
  display: 'flex', flexDirection: 'column', gap: 8, width: '100%', maxWidth: 480, minWidth: 0, boxSizing: 'border-box', overflowWrap: 'anywhere',
}
const headerRow: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', minWidth: 0 }
const badgeStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--ink-3)', border: '1px solid var(--line)', borderRadius: 4, padding: '2px 6px' }
const titleStyle: CSSProperties = { fontWeight: 600, minWidth: 0 }
const fieldStyle: CSSProperties = { margin: 0, lineHeight: 1.5 }
const ulStyle: CSSProperties = { margin: '2px 0', paddingLeft: 18 }
const preparedBox: CSSProperties = { borderTop: '1px solid var(--line)', paddingTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }
const statusBox: CSSProperties = { background: '#4CAF5011', border: '1px solid #4CAF50', borderRadius: 8, padding: 8, color: '#2e7d32', display: 'flex', flexDirection: 'column', gap: 4 }
const evidenceStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11 }
const recoveryRow: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }
const actionRow: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }
const errorText: CSSProperties = { color: '#F44336', fontSize: 11 }
const btnBase: CSSProperties = { background: 'none', border: '1px solid var(--line)', borderRadius: 4, padding: '4px 10px', minHeight: 44, cursor: 'pointer', color: 'var(--ink)', fontFamily: 'var(--font-mono)', fontSize: 11 }
const btnPrimary: CSSProperties = { ...btnBase, background: 'var(--primary)', color: 'var(--on-primary)', borderColor: 'var(--primary)' }
const refreshButton: CSSProperties = { ...btnBase, alignSelf: 'flex-start' }
