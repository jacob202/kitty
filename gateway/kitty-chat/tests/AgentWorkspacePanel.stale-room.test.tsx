import { act, cleanup, render, screen } from '@testing-library/react'
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

function runningWorkspace(): AgentWorkspace {
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
      { id: 'builder', display_name: 'Builder', role: 'builder', model: 'kitty-default', status: 'available' },
      { id: 'reviewer', display_name: 'Reviewer', role: 'reviewer', model: 'kitty-sonnet', status: 'available' },
    ],
    messages: [],
    events: [],
    turns: [{
      id: 'turn_running', workspace_id: 'workspace_test', user_message_id: 'message_user',
      status: 'running', active_agent_id: 'researcher', error_type: null,
      error_message: null, started_at: 1, finished_at: null,
    }],
  }
}

describe('AgentWorkspacePanel stale loaded room recovery', () => {
  it('drops cached running state when a later poll definitively 404s', async () => {
    vi.useFakeTimers()
    const running = runningWorkspace()
    window.localStorage.setItem('kitty.agent-workspace-id', running.id)
    fetchAgentWorkspace
      .mockResolvedValueOnce(running)
      .mockRejectedValue(new Error('Gateway returned 404 Not Found'))

    render(<AgentWorkspacePanel />)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('researcher is working. Partial messages are saved as they arrive.')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(1_000)
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(screen.getByRole('heading', { name: 'This room no longer exists' })).toBeInTheDocument()
    const callsAfter404 = fetchAgentWorkspace.mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(3_000)
      await Promise.resolve()
    })
    expect(fetchAgentWorkspace).toHaveBeenCalledTimes(callsAfter404)
  })
})
