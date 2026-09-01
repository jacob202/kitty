import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentWorkspacePanel } from '../src/components/AgentWorkspacePanel'
import type { AgentRoomInboxMessage, AgentWorkspace, AgentWorkspaceMessage } from '../src/lib/gateway'

const fetchGlobalAgentRoom = vi.hoisted(() => vi.fn())
const fetchGlobalAgentMessages = vi.hoisted(() => vi.fn())
const fetchGlobalAgentInbox = vi.hoisted(() => vi.fn())
const fetchGlobalAgentThread = vi.hoisted(() => vi.fn())
const postGlobalAgentMessage = vi.hoisted(() => vi.fn())
const updateGlobalAgentReceipt = vi.hoisted(() => vi.fn())

vi.mock('../src/lib/gateway', () => ({
  fetchGlobalAgentRoom,
  fetchGlobalAgentMessages,
  fetchGlobalAgentInbox,
  fetchGlobalAgentThread,
  postGlobalAgentMessage,
  updateGlobalAgentReceipt,
}))

function room(): AgentWorkspace {
  return {
    id: 'workspace_global', name: 'Global Agent Room', objective: null, status: 'active',
    created_at: 1, updated_at: 1,
    agents: [
      { id: 'chatgpt', display_name: 'ChatGPT', role: 'external', model: null, status: 'registered' },
      { id: 'claude', display_name: 'Claude', role: 'external', model: null, status: 'registered' },
      { id: 'codex', display_name: 'Codex', role: 'external', model: null, status: 'registered' },
      { id: 'kitty', display_name: 'Kitty', role: 'principal', model: null, status: 'registered' },
    ], messages: [], events: [], turns: [],
  }
}

function message(overrides: Partial<AgentWorkspaceMessage> = {}): AgentWorkspaceMessage {
  return {
    id: 'm1', workspace_id: 'workspace_global', parent_message_id: null,
    sender_kind: 'agent', sender_id: 'claude', recipient_id: 'jacob',
    message_kind: 'review', content: 'Incoming.', created_at: 2, ...overrides,
  }
}

function inbox(overrides: Partial<AgentRoomInboxMessage> = {}): AgentRoomInboxMessage {
  return { ...message(), seen_at: null, acknowledged_at: null, receipt_state: 'sent', ...overrides }
}

beforeEach(() => {
  fetchGlobalAgentRoom.mockResolvedValue(room())
  fetchGlobalAgentMessages.mockResolvedValue([])
  fetchGlobalAgentInbox.mockResolvedValue([])
  fetchGlobalAgentThread.mockResolvedValue([])
  postGlobalAgentMessage.mockResolvedValue(message({
    id: 'posted', sender_kind: 'user', sender_id: 'jacob', recipient_id: 'codex', content: 'Posted.', created_at: 4,
  }))
  updateGlobalAgentReceipt.mockResolvedValue({
    message_id: 'm1', participant_id: 'jacob', seen_at: 3, acknowledged_at: 3, receipt_state: 'acknowledged',
  })
})

afterEach(() => {
  vi.useRealTimers()
  cleanup()
  vi.clearAllMocks()
})

describe('AgentWorkspacePanel review regressions', () => {
  it('does not claim a durable registered room when the initial room load fails', async () => {
    fetchGlobalAgentRoom.mockRejectedValueOnce(new Error('Gateway returned 503 Service Unavailable'))
    render(<AgentWorkspacePanel />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry Global Agent Room' })).toBeInTheDocument())
    expect(screen.queryByText('durable room')).not.toBeInTheDocument()
    expect(screen.queryAllByText('registered')).toHaveLength(0)
    expect(screen.queryByLabelText('Recipient')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/Could not load the Global Agent Room/)
    expect(screen.queryByText(/Gateway returned|503/i)).not.toBeInTheDocument()
  })

  it('renders inbox-only messages so unread items can be inspected and acknowledged', async () => {
    const incoming = inbox({ id: 'inbox-only', content: 'Older direct message.' })
    fetchGlobalAgentInbox.mockResolvedValue([incoming])
    render(<AgentWorkspacePanel />)

    await waitFor(() => expect(screen.getByText('Older direct message.')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Acknowledge message from Claude' })).toBeInTheDocument()
  })

  it('allows a seen but unacknowledged inbox message to be acknowledged', async () => {
    const seen = inbox({ id: 'seen-only', seen_at: 3, acknowledged_at: null, receipt_state: 'seen' })
    fetchGlobalAgentMessages.mockResolvedValue([seen])
    fetchGlobalAgentInbox.mockResolvedValue([seen])
    render(<AgentWorkspacePanel />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Acknowledge message from Claude' })).toBeInTheDocument())
  })

  it('loads missing reply parent context from the durable thread endpoint', async () => {
    const root = message({ id: 'root-old', content: 'Older parent context.' })
    const reply = message({ id: 'reply-new', sender_id: 'codex', parent_message_id: root.id, content: 'Recent reply.' })
    fetchGlobalAgentMessages.mockResolvedValue([reply])
    fetchGlobalAgentThread.mockResolvedValue([root, reply])
    render(<AgentWorkspacePanel />)

    await waitFor(() => expect(screen.getByText(/Reply to Claude · Older parent context\./)).toBeInTheDocument())
    expect(fetchGlobalAgentThread).toHaveBeenCalledWith('reply-new', 100)
  })

  it('does not let a stale in-flight poll erase a newly posted message', async () => {
    vi.useFakeTimers()
    const old = message({ id: 'old', content: 'Old transcript.' })
    fetchGlobalAgentMessages.mockResolvedValueOnce([old])
    render(<AgentWorkspacePanel />)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })

    let resolvePoll!: (value: AgentWorkspaceMessage[]) => void
    const stalePoll = new Promise<AgentWorkspaceMessage[]>((resolve) => { resolvePoll = resolve })
    fetchGlobalAgentMessages.mockReturnValueOnce(stalePoll)
    await act(async () => { vi.advanceTimersByTime(3_000); await Promise.resolve() })

    fireEvent.change(screen.getByPlaceholderText('Message the room or an agent…'), { target: { value: 'Posted.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('Posted.')).toBeInTheDocument()

    await act(async () => { resolvePoll([old]); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('Posted.')).toBeInTheDocument()
  })

  it('keeps a send failure visible across a later successful poll', async () => {
    vi.useFakeTimers()
    const incoming = message({ content: 'Stable transcript.' })
    fetchGlobalAgentMessages.mockResolvedValue([incoming])
    postGlobalAgentMessage.mockRejectedValueOnce(new Error('Gateway returned 409 Conflict'))
    render(<AgentWorkspacePanel />)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })

    fireEvent.change(screen.getByPlaceholderText('Message the room or an agent…'), { target: { value: 'Rejected draft.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByRole('alert')).toHaveTextContent(/Could not send the message/)

    await act(async () => { vi.advanceTimersByTime(3_000); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByRole('alert')).toHaveTextContent(/Could not send the message/)
    expect(screen.getByPlaceholderText('Message the room or an agent…')).toHaveValue('Rejected draft.')
  })
})
