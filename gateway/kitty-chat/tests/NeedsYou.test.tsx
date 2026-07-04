import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { NeedsYou } from '../src/components/NeedsYou'
import type { GatewayAction, GatewayTriageEntry } from '../src/lib/gateway'

describe('NeedsYou', () => {
  afterEach(cleanup)

  const action: GatewayAction = {
    id: 1,
    created_at: 0,
    source_kind: 'inbox',
    source_id: null,
    kind: 'draft_reply',
    title: 'Reply to landlord',
    preview: 'Draft a reply about the lease renewal.',
    payload: {},
    risk_tier: 'T2',
    status: 'proposed',
    result: null,
    decided_at: null,
    executed_at: null,
  }

  const triageEntry: GatewayTriageEntry = {
    inbox_id: '42',
    ts: 0,
    bucket: 'needs_jacob',
    confidence: 0.4,
    rationale: 'Ambiguous whether this is spam or a real invoice.',
    model: 'kitty-smart',
    text: 'Invoice #881 attached — please review.',
    created_at: 0,
  }

  it('shows an honest empty state when nothing needs Jacob', () => {
    render(
      <NeedsYou
        actions={[]}
        actionsError={null}
        needsJacob={[]}
        needsJacobError={null}
        onApprove={() => {}}
        onReject={() => {}}
        onDecideInChat={() => {}}
      />
    )
    expect(screen.getByText('Nothing needs you right now.')).toBeInTheDocument()
  })

  it('renders proposed actions with working approve/reject buttons', () => {
    const onApprove = vi.fn()
    const onReject = vi.fn()
    render(
      <NeedsYou
        actions={[action]}
        actionsError={null}
        needsJacob={[]}
        needsJacobError={null}
        onApprove={onApprove}
        onReject={onReject}
        onDecideInChat={() => {}}
      />
    )
    expect(screen.getByText('Reply to landlord')).toBeInTheDocument()
    fireEvent.click(screen.getByText('approve'))
    expect(onApprove).toHaveBeenCalledWith(1)
    fireEvent.click(screen.getByText('reject'))
    expect(onReject).toHaveBeenCalledWith(1)
  })

  it('renders needs_jacob triage items with a decide-in-chat verb', () => {
    const onDecideInChat = vi.fn()
    render(
      <NeedsYou
        actions={[]}
        actionsError={null}
        needsJacob={[triageEntry]}
        needsJacobError={null}
        onApprove={() => {}}
        onReject={() => {}}
        onDecideInChat={onDecideInChat}
      />
    )
    expect(screen.getByText(/Invoice #881/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('decide in chat'))
    expect(onDecideInChat).toHaveBeenCalledWith(triageEntry)
  })

  it('shows an honest error state when the gateway is unreachable, not a fabricated empty list', () => {
    render(
      <NeedsYou
        actions={[]}
        actionsError="Request timed out — is the Kitty gateway running?"
        needsJacob={[]}
        needsJacobError="Request timed out — is the Kitty gateway running?"
        onApprove={() => {}}
        onReject={() => {}}
        onDecideInChat={() => {}}
      />
    )
    expect(screen.getByRole('alert')).toHaveTextContent("Can't reach the gateway")
    expect(screen.queryByText('Nothing needs you right now.')).not.toBeInTheDocument()
  })
})
