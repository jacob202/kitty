'use client'

import { useState, type CSSProperties } from 'react'
import { useProposeBuilderJob, useApproveBuilderJob } from '@/lib/queries'
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

export function BuilderProposalCard({ task }: { task: BuilderProposalTask }) {
  const propose = useProposeBuilderJob()
  const approve = useApproveBuilderJob()
  const [proposal, setProposal] = useState<ConversationProposal | null>(null)
  const [confirming, setConfirming] = useState(false)

  const approved = approve.data?.ok === true

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
    approve.mutate({
      prepared_manifest: proposal.prepared_manifest,
      expected_manifest_sha: proposal.manifest_sha256,
      expected_base_sha: proposal.expected_base_sha,
      approval_nonce: proposal.approval_nonce,
      confirmed: true,
    })
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

      {!proposal && !approved && (
        <button type="button" onClick={doPropose} disabled={propose.isPending} style={btnPrimary}>
          {propose.isPending ? 'Compiling…' : 'Compile as Builder Mission'}
        </button>
      )}

      {propose.isError && (
        <span style={errorText}>{propose.error instanceof Error ? propose.error.message : 'propose failed'}</span>
      )}

      {proposal && !proposal.ok && (
        <span style={errorText}>{proposal.error || 'proposal was refused'}</span>
      )}

      {proposal?.ok && !approved && (
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
        <span style={errorText}>{approve.error instanceof Error ? approve.error.message : 'approve failed'}</span>
      )}
      {approve.data && !approve.data.ok && (
        <span style={errorText}>{approve.data.error || 'approval was refused'}</span>
      )}

      {approved && (
        <div style={successBox}>
          Builder job created: <strong>{approve.data?.mission_id}</strong>.
          Track it in the Work view — Kitty&apos;s chat does not run or report on it directly.
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
