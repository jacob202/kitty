import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AgentWorkspacePanel } from '../src/components/AgentWorkspacePanel'

const fetchGlobalAgentRoom = vi.hoisted(() => vi.fn())
const fetchGlobalAgentMessages = vi.hoisted(() => vi.fn())
const fetchGlobalAgentInbox = vi.hoisted(() => vi.fn())
const postGlobalAgentMessage = vi.hoisted(() => vi.fn())
const updateGlobalAgentReceipt = vi.hoisted(() => vi.fn())
vi.mock('../src/lib/gateway', () => ({ fetchGlobalAgentRoom, fetchGlobalAgentMessages, fetchGlobalAgentInbox, postGlobalAgentMessage, updateGlobalAgentReceipt }))

beforeEach(() => {
  fetchGlobalAgentRoom.mockResolvedValue({ id: 'workspace_global', name: 'Global Agent Room', objective: null, status: 'active', created_at: 1, updated_at: 1, agents: [], messages: [], events: [], turns: [] })
  fetchGlobalAgentMessages
    .mockResolvedValueOnce([{ id: 'm1', workspace_id: 'workspace_global', parent_message_id: null, sender_kind: 'agent', sender_id: 'claude', recipient_id: 'jacob', message_kind: 'review', content: 'Durable transcript.', created_at: 1 }])
    .mockRejectedValueOnce(new Error('temporary gateway disconnect'))
    .mockResolvedValueOnce([{ id: 'm1', workspace_id: 'workspace_global', parent_message_id: null, sender_kind: 'agent', sender_id: 'claude', recipient_id: 'jacob', message_kind: 'review', content: 'Durable transcript.', created_at: 1 }])
  fetchGlobalAgentInbox.mockResolvedValue([])
  vi.useFakeTimers()
})
afterEach(() => { vi.useRealTimers(); cleanup(); vi.clearAllMocks() })

it('keeps the last transcript visible across a transient polling failure and retries', async () => {
  render(<AgentWorkspacePanel />)
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
  expect(screen.getByText('Durable transcript.')).toBeInTheDocument()

  await act(async () => { vi.advanceTimersByTime(3_000); await Promise.resolve(); await Promise.resolve() })
  expect(screen.getByText('Durable transcript.')).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Could not refresh the Global Agent Room. Something went wrong.')
  expect(screen.queryByText('temporary gateway disconnect')).not.toBeInTheDocument()

  await act(async () => { vi.advanceTimersByTime(3_000); await Promise.resolve(); await Promise.resolve() })
  expect(fetchGlobalAgentMessages).toHaveBeenCalledTimes(3)
  expect(screen.getByText('Durable transcript.')).toBeInTheDocument()
})
