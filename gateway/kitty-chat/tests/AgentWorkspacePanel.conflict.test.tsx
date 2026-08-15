import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  cleanup()
  window.localStorage.clear()
  createAgentWorkspace.mockReset()
  fetchAgentWorkspace.mockReset()
  runAgentWorkspaceTurn.mockReset()
})

function workspace(turns: AgentWorkspace['turns'] = []): AgentWorkspace {
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
    turns,
  }
}

describe('AgentWorkspacePanel submission reconciliation', () => {
  it('reloads durable room state after a rejected cross-tab submission', async () => {
    const idle = workspace()
    const running = workspace([{
      id: 'turn_other_tab', workspace_id: idle.id, user_message_id: 'message_other_tab',
      status: 'running', active_agent_id: 'planner', error_type: null,
      error_message: null, started_at: 2, finished_at: null,
    }])
    window.localStorage.setItem('kitty.agent-workspace-id', idle.id)
    fetchAgentWorkspace.mockResolvedValueOnce(idle).mockResolvedValueOnce(running)
    runAgentWorkspaceTurn.mockRejectedValue(new Error('Gateway returned 409 Conflict'))

    render(<AgentWorkspacePanel />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Kitty Shared Room' })).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText('Ask the room to plan, research, and review…'), {
      target: { value: 'Please do the next step.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'send to room' }))

    await waitFor(() => expect(fetchAgentWorkspace).toHaveBeenCalledTimes(2))
    expect(screen.getByText('planner is working. Partial messages are saved as they arrive.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Gateway returned 409 Conflict')
    expect(screen.getByPlaceholderText('Ask the room to plan, research, and review…')).toHaveValue('Please do the next step.')
  })
})
