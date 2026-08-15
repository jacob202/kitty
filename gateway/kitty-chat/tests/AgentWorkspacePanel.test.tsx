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
    runAgentWorkspaceTurn.mockResolvedValue({
      status: 'completed', workspace_id: created.id,
      messages: completed.messages, events: completed.events,
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
})
