import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AgentWorkspacePanel } from '../src/components/AgentWorkspacePanel'

const fetchGlobalAgentRoom = vi.hoisted(() => vi.fn())
const fetchGlobalAgentMessages = vi.hoisted(() => vi.fn())
const fetchGlobalAgentInbox = vi.hoisted(() => vi.fn())
const postGlobalAgentMessage = vi.hoisted(() => vi.fn())
const updateGlobalAgentReceipt = vi.hoisted(() => vi.fn())
vi.mock('../src/lib/gateway', () => ({ fetchGlobalAgentRoom, fetchGlobalAgentMessages, fetchGlobalAgentInbox, postGlobalAgentMessage, updateGlobalAgentReceipt }))

beforeEach(() => {
  fetchGlobalAgentRoom.mockResolvedValue({
    id: 'workspace_global', name: 'Global Agent Room', objective: null, status: 'active', created_at: 1, updated_at: 1,
    agents: [{ id: 'codex', display_name: 'Codex', role: 'external', model: null, status: 'registered' }], messages: [], events: [], turns: [],
  })
  fetchGlobalAgentMessages.mockResolvedValue([{ id: 'root', workspace_id: 'workspace_global', parent_message_id: null, sender_kind: 'agent', sender_id: 'codex', recipient_id: 'jacob', message_kind: 'review', content: 'Please reply.', created_at: 1 }])
  fetchGlobalAgentInbox.mockResolvedValue([])
  postGlobalAgentMessage.mockRejectedValue(new Error('Gateway returned 409 Conflict'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('preserves draft and reply context when a post is rejected', async () => {
  render(<AgentWorkspacePanel />)
  await waitFor(() => expect(screen.getByText('Please reply.')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: 'Reply to Codex' }))
  const composer = screen.getByPlaceholderText('Message the room or an agent…')
  fireEvent.change(composer, { target: { value: 'Still working on it.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent("Could not send the message. Kitty couldn't complete that request."))
  expect(screen.queryByText(/Gateway returned/i)).not.toBeInTheDocument()
  expect(composer).toHaveValue('Still working on it.')
  expect(screen.getByText('Replying to Codex')).toBeInTheDocument()
})
