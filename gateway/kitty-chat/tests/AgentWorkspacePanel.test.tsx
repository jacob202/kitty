import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentWorkspacePanel } from '../src/components/AgentWorkspacePanel'
import type { AgentRoomInboxMessage, AgentWorkspace, AgentWorkspaceMessage } from '../src/lib/gateway'

const fetchGlobalAgentRoom = vi.hoisted(() => vi.fn())
const fetchGlobalAgentMessages = vi.hoisted(() => vi.fn())
const fetchGlobalAgentInbox = vi.hoisted(() => vi.fn())
const postGlobalAgentMessage = vi.hoisted(() => vi.fn())
const updateGlobalAgentReceipt = vi.hoisted(() => vi.fn())

vi.mock('../src/lib/gateway', () => ({
  fetchGlobalAgentRoom,
  fetchGlobalAgentMessages,
  fetchGlobalAgentInbox,
  postGlobalAgentMessage,
  updateGlobalAgentReceipt,
}))

function globalRoom(
  messages: AgentWorkspaceMessage[] = [],
  agents?: AgentWorkspace['agents'],
): AgentWorkspace {
  return {
    id: 'workspace_global',
    name: 'Global Agent Room',
    objective: 'Shared durable coordination for Jacob and authorized agents.',
    status: 'active', created_at: 1, updated_at: 1,
    agents: agents ?? [
      { id: 'chatgpt', display_name: 'ChatGPT', role: 'external', model: null, status: 'registered' },
      { id: 'claude', display_name: 'Claude', role: 'external', model: null, status: 'registered' },
      { id: 'codex', display_name: 'Codex', role: 'external', model: null, status: 'registered' },
      { id: 'kitty', display_name: 'Kitty', role: 'principal', model: null, status: 'registered' },
    ],
    messages, events: [], turns: [],
  }
}

function message(overrides: Partial<AgentWorkspaceMessage> = {}): AgentWorkspaceMessage {
  return {
    id: 'message_1', workspace_id: 'workspace_global', parent_message_id: null,
    sender_kind: 'agent', sender_id: 'claude', recipient_id: 'jacob',
    message_kind: 'review', content: 'Review complete.', created_at: 2,
    ...overrides,
  }
}

function inboxMessage(overrides: Partial<AgentRoomInboxMessage> = {}): AgentRoomInboxMessage {
  return {
    ...message(), seen_at: null, acknowledged_at: null, receipt_state: 'sent', ...overrides,
  }
}

beforeEach(() => {
  fetchGlobalAgentRoom.mockResolvedValue(globalRoom())
  fetchGlobalAgentMessages.mockResolvedValue([])
  fetchGlobalAgentInbox.mockResolvedValue([])
  postGlobalAgentMessage.mockResolvedValue(message({ id: 'message_posted', sender_kind: 'user', sender_id: 'jacob' }))
  updateGlobalAgentReceipt.mockResolvedValue({
    message_id: 'message_1', participant_id: 'jacob', seen_at: 3,
    acknowledged_at: 3, receipt_state: 'acknowledged',
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AgentWorkspacePanel global command center', () => {
  it('auto-loads workspace_global and shows membership without fake online presence', async () => {
    render(<AgentWorkspacePanel />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Global Agent Room' })).toBeInTheDocument())
    expect(fetchGlobalAgentRoom).toHaveBeenCalledTimes(1)
    expect(screen.getByText('ChatGPT')).toBeInTheDocument()
    expect(screen.getByText('Claude')).toBeInTheDocument()
    expect(screen.getAllByText('registered')).toHaveLength(4)
    expect(screen.queryByText(/online/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /create shared room/i })).not.toBeInTheDocument()
  })

  it('renders participants added after this component was written, by name not raw id', async () => {
    // Regression: CANONICAL_AGENTS was a hardcoded copy of the roster that had
    // already gone stale (it omitted DSH), so any newer sender rendered as a
    // bare id in the transcript and could not be chosen as a DM recipient.
    // The live room response is now the only source of truth.
    fetchGlobalAgentRoom.mockResolvedValue(globalRoom([], [
      { id: 'chatgpt', display_name: 'ChatGPT', role: 'external', model: null, status: 'registered' },
      { id: 'dsh', display_name: 'DSH', role: 'principal', model: null, status: 'registered' },
      { id: 'commandcode', display_name: 'Command Code', role: 'external', model: null, status: 'registered' },
    ]))

    render(<AgentWorkspacePanel />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Global Agent Room' })).toBeInTheDocument())

    expect(screen.getByText('DSH')).toBeInTheDocument()
    expect(screen.getByText('Command Code')).toBeInTheDocument()
    expect(screen.queryByText('commandcode')).not.toBeInTheDocument()

    // Selectable as a direct-message recipient even though the old list never knew it.
    const recipient = screen.getByLabelText('Recipient') as HTMLSelectElement
    expect(Array.from(recipient.options).map((option) => option.value)).toContain('commandcode')
    expect(screen.getByText('Direct · Command Code')).toBeInTheDocument()
  })

  it('derives the header member count from the response instead of stating a fixed number', async () => {
    // Six participants, one of them retired; the old pill claimed a fixed count
    // regardless, contradicting the cards rendered beside it.
    fetchGlobalAgentRoom.mockResolvedValue(globalRoom([], [
      { id: 'chatgpt', display_name: 'ChatGPT', role: 'external', model: null, status: 'registered' },
      { id: 'claude', display_name: 'Claude', role: 'external', model: null, status: 'retired' },
      { id: 'codex', display_name: 'Codex', role: 'external', model: null, status: 'registered' },
      { id: 'kitty', display_name: 'Kitty', role: 'principal', model: null, status: 'registered' },
      { id: 'dsh', display_name: 'DSH', role: 'principal', model: null, status: 'registered' },
      { id: 'commandcode', display_name: 'Command Code', role: 'external', model: null, status: 'registered' },
    ]))

    render(<AgentWorkspacePanel />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Global Agent Room' })).toBeInTheDocument())

    expect(screen.getByText('6 agents · 5 registered · 1 retired')).toBeInTheDocument()
    expect(screen.queryByText(/four registered agents/i)).not.toBeInTheDocument()
  })

  it('labels each roster entry with the status the room actually reports', async () => {
    fetchGlobalAgentRoom.mockResolvedValue(globalRoom([], [
      { id: 'chatgpt', display_name: 'ChatGPT', role: 'external', model: null, status: 'registered' },
      { id: 'claude', display_name: 'Claude', role: 'external', model: null, status: 'retired' },
    ]))

    render(<AgentWorkspacePanel />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Global Agent Room' })).toBeInTheDocument())

    // Previously every card said "registered" regardless of the real status.
    expect(screen.getByText('retired')).toBeInTheDocument()
    expect(screen.getAllByText('registered')).toHaveLength(1)
  })

  it('sends a direct message from Jacob to the selected agent', async () => {
    render(<AgentWorkspacePanel />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Global Agent Room' })).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Recipient'), { target: { value: 'claude' } })
    fireEvent.change(screen.getByPlaceholderText('Message the room or an agent…'), {
      target: { value: 'Please review PR #751.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => expect(postGlobalAgentMessage).toHaveBeenCalledWith({
      recipientId: 'claude', content: 'Please review PR #751.',
      messageKind: 'prompt', parentMessageId: null,
    }))
  })

  it('replies in-thread and automatically targets the original sender', async () => {
    const root = message({ id: 'message_root', sender_id: 'codex', content: 'I found one issue.' })
    fetchGlobalAgentMessages.mockResolvedValue([root])
    render(<AgentWorkspacePanel />)
    await waitFor(() => expect(screen.getByText('I found one issue.')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Reply to Codex' }))
    expect(screen.getByText('Replying to Codex')).toBeInTheDocument()
    expect(screen.getByLabelText('Recipient')).toHaveValue('codex')
    fireEvent.change(screen.getByPlaceholderText('Message the room or an agent…'), {
      target: { value: 'Good catch.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => expect(postGlobalAgentMessage).toHaveBeenCalledWith({
      recipientId: 'codex', content: 'Good catch.', messageKind: 'prompt',
      parentMessageId: 'message_root',
    }))
  })

  it('acknowledges Jacob inbox messages explicitly and keeps ack separate from completion', async () => {
    const incoming = inboxMessage({ content: 'Need your acknowledgement.' })
    fetchGlobalAgentMessages.mockResolvedValue([incoming])
    fetchGlobalAgentInbox.mockResolvedValue([incoming])
    render(<AgentWorkspacePanel />)

    await waitFor(() => expect(screen.getByText('1 unread')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge message from Claude' }))

    await waitFor(() => expect(updateGlobalAgentReceipt).toHaveBeenCalledWith('message_1', 'acknowledged'))
    expect(screen.queryByText(/completed/i)).not.toBeInTheDocument()
  })
})
