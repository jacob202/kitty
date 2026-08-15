import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentWorkspacePanel } from '../src/components/AgentWorkspacePanel'
import type { AgentWorkspace } from '../src/lib/gateway'

const createAgentWorkspace = vi.hoisted(() => vi.fn())
const fetchAgentWorkspace = vi.hoisted(() => vi.fn())
const runAgentWorkspaceTurn = vi.hoisted(() => vi.fn())

vi.mock('../src/lib/gateway', () => ({
  createAgentWorkspace,
  fetchAgentWorkspace,
  runAgentWorkspaceTurn,
}))

beforeEach(() => {
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear(),
    },
  })
})

afterEach(() => {
  vi.useRealTimers()
  cleanup()
  window.localStorage.clear()
  createAgentWorkspace.mockReset()
  fetchAgentWorkspace.mockReset()
  runAgentWorkspaceTurn.mockReset()
})

function workspace(messages: AgentWorkspace['messages'] = []): AgentWorkspace {
  return {
    id: 'workspace_test',
    name: 'Kitty Shared Room',
    objective: 'Coordinate a verified outcome with dedicated agents.',
    status: 'active',
    created_at: 1,
    updated_at: 1,
    agents: [
      { id: 'planner', display_name: 'Planner', role: 'planner', model: 'kitty-sonnet', status: 'available' },
      { id: 'researcher', display_name: 'Researcher', role: 'researcher', model: 'kitty-default', status: 'available' },
      { id: 'builder', display_name: 'Builder', role: 'builder', model: 'deepseek/deepseek-v4-flash', status: 'available' },
      { id: 'reviewer', display_name: 'Reviewer', role: 'reviewer', model: 'kitty-sonnet', status: 'available' },
    ],
    messages,
    events: [],
    turns: [],
  }
}

describe('AgentWorkspacePanel', () => {
  it('creates a room and renders the durable agent handoff transcript', async () => {
    const created = workspace()
    const completed = workspace([
      {
        id: 'message_user', workspace_id: created.id, parent_message_id: null,
        sender_kind: 'user', sender_id: 'jacob', recipient_id: null,
        message_kind: 'prompt', content: 'Plan a verified outcome.', created_at: 1,
      },
      {
        id: 'message_planner', workspace_id: created.id, parent_message_id: 'message_user',
        sender_kind: 'agent', sender_id: 'planner', recipient_id: 'researcher',
        message_kind: 'plan', content: 'planner response', created_at: 2,
      },
      {
        id: 'message_reviewer', workspace_id: created.id, parent_message_id: 'message_planner',
        sender_kind: 'agent', sender_id: 'reviewer', recipient_id: 'jacob',
        message_kind: 'review', content: 'review response', created_at: 3,
      },
    ])
    createAgentWorkspace.mockResolvedValue(created)
    fetchAgentWorkspace.mockResolvedValue(completed)
    runAgentWorkspaceTurn.mockResolvedValue({
      status: 'running', workspace_id: created.id,
      turn: {
        id: 'turn_running', workspace_id: created.id, user_message_id: 'message_user',
        status: 'running', active_agent_id: 'planner', error_type: null,
        error_message: null, started_at: 1, finished_at: null,
      },
    })

    render(<AgentWorkspacePanel />)
    fireEvent.click(screen.getByRole('button', { name: 'create shared room' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Kitty Shared Room' })).toBeInTheDocument())
    expect(screen.getByText('Planner')).toBeInTheDocument()
    expect(screen.getByText('Builder')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('Ask the room to plan, research, and review…'), {
      target: { value: 'Plan a verified outcome.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'send to room' }))

    await waitFor(() => expect(screen.getByText('planner response')).toBeInTheDocument())
    expect(screen.getByText('review response')).toBeInTheDocument()
    expect(runAgentWorkspaceTurn).toHaveBeenCalledWith(created.id, 'Plan a verified outcome.')
  })

  it('labels Builder handoffs as proposals and keeps a durable failed turn visible', async () => {
    const failed = {
      ...workspace([
        {
          id: 'message_user', workspace_id: 'workspace_test', parent_message_id: null,
          sender_kind: 'user' as const, sender_id: 'jacob', recipient_id: null,
          message_kind: 'prompt' as const, content: 'Plan a verified outcome.', created_at: 1,
        },
        {
          id: 'message_builder', workspace_id: 'workspace_test', parent_message_id: 'message_user',
          sender_kind: 'agent' as const, sender_id: 'builder', recipient_id: 'reviewer',
          message_kind: 'handoff' as const, content: 'Builder proposal only.', created_at: 2,
        },
        {
          id: 'message_failure', workspace_id: 'workspace_test', parent_message_id: 'message_builder',
          sender_kind: 'system' as const, sender_id: 'gateway', recipient_id: 'jacob',
          message_kind: 'status' as const, content: 'Incomplete: reviewer could not finish.', created_at: 3,
        },
      ]),
      turns: [{
        id: 'turn_failed', workspace_id: 'workspace_test', user_message_id: 'message_user',
        status: 'failed', active_agent_id: null, error_type: 'RuntimeError',
        error_message: 'provider rejected the request', started_at: 1, finished_at: 2,
      }],
    } as AgentWorkspace
    createAgentWorkspace.mockResolvedValue(failed)

    render(<AgentWorkspacePanel />)
    fireEvent.click(screen.getByRole('button', { name: 'create shared room' }))

    await waitFor(() => expect(screen.getByText('builder proposal')).toBeInTheDocument())
    expect(screen.getByText('Incomplete: reviewer could not finish.')).toBeInTheDocument()
    expect(screen.getByText('Incomplete: provider rejected the request')).toBeInTheDocument()
    expect(screen.queryByText(/RuntimeError/)).not.toBeInTheDocument()
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('refreshes a running room so status changes appear without resending the request', async () => {
    const running = {
      ...workspace(),
      turns: [{
        id: 'turn_running', workspace_id: 'workspace_test', user_message_id: 'message_user',
        status: 'running', active_agent_id: 'researcher', error_type: null,
        error_message: null, started_at: 1, finished_at: null,
      }],
    }
    const completed = {
      ...workspace(),
      turns: [{
        id: 'turn_running', workspace_id: 'workspace_test', user_message_id: 'message_user',
        status: 'completed', active_agent_id: null, error_type: null,
        error_message: null, started_at: 1, finished_at: 2,
      }],
    }
    window.localStorage.setItem('kitty.agent-workspace-id', running.id)
    fetchAgentWorkspace.mockResolvedValueOnce(running).mockResolvedValueOnce(completed)
    vi.useFakeTimers()

    render(<AgentWorkspacePanel />)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('researcher is working. Partial messages are saved as they arrive.')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(1_000)
      await Promise.resolve()
    })

    expect(fetchAgentWorkspace).toHaveBeenCalledTimes(2)
    expect(screen.getByText('completed')).toBeInTheDocument()
  })

  it('keeps a running transcript visible and retries after a transient polling failure', async () => {
    const running = {
      ...workspace([
        {
          id: 'message_planner', workspace_id: 'workspace_test', parent_message_id: null,
          sender_kind: 'agent' as const, sender_id: 'planner', recipient_id: 'researcher',
          message_kind: 'plan' as const, content: 'Durable partial plan.', created_at: 1,
        },
      ]),
      turns: [{
        id: 'turn_running', workspace_id: 'workspace_test', user_message_id: 'message_user',
        status: 'running', active_agent_id: 'researcher', error_type: null,
        error_message: null, started_at: 1, finished_at: null,
      }],
    }
    const completed = {
      ...running,
      turns: [{
        ...running.turns[0], status: 'completed' as const, active_agent_id: null, finished_at: 2,
      }],
    }
    window.localStorage.setItem('kitty.agent-workspace-id', running.id)
    fetchAgentWorkspace
      .mockResolvedValueOnce(running)
      .mockRejectedValueOnce(new Error('temporary gateway disconnect'))
      .mockResolvedValueOnce(completed)
    vi.useFakeTimers()

    render(<AgentWorkspacePanel />)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('Durable partial plan.')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(1_000)
      await Promise.resolve()
    })
    expect(screen.getByText('Durable partial plan.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('temporary gateway disconnect')

    await act(async () => {
      vi.advanceTimersByTime(1_000)
      await Promise.resolve()
    })
    expect(fetchAgentWorkspace).toHaveBeenCalledTimes(3)
    expect(screen.getByText('completed')).toBeInTheDocument()
  })

  it('offers a reset path and recovers when the saved room id 404s', async () => {
    window.localStorage.setItem('kitty.agent-workspace-id', 'workspace_missing')
    fetchAgentWorkspace.mockRejectedValue(new Error('Gateway returned 404 Not Found'))
    const created = workspace()
    createAgentWorkspace.mockResolvedValue(created)

    render(<AgentWorkspacePanel />)

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'This room no longer exists' })).toBeInTheDocument()
    )
    // A stale/missing id must not trap the user behind a "retry" that can never succeed.
    expect(screen.queryByRole('button', { name: 'retry room' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'start a new room' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'create shared room' })).toBeInTheDocument()
    )
    expect(window.localStorage.getItem('kitty.agent-workspace-id')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'create shared room' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Kitty Shared Room' })).toBeInTheDocument())
  })
})
