import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentPanel } from '../src/components/AgentPanel'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    fetchAgentSessions: vi.fn(),
    fetchAgentStatus: vi.fn(),
    spawnAgent: vi.fn(),
    stopAgent: vi.fn(),
  }
})

const session: gateway.AgentSession = {
  session_id: 17,
  goal: 'check the repo',
  agent_type: 'reviewer',
  status: 'running',
  created_at: '2026-08-17T00:00:00Z',
}

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

describe('AgentPanel fail-loud behavior', () => {
  beforeEach(() => {
    vi.mocked(gateway.fetchAgentSessions).mockResolvedValue([session])
    vi.mocked(gateway.fetchAgentStatus).mockResolvedValue(session)
    vi.mocked(gateway.spawnAgent).mockResolvedValue(18)
    vi.mocked(gateway.stopAgent).mockResolvedValue(undefined)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('does not render a gateway failure as no agents yet', async () => {
    vi.mocked(gateway.fetchAgentSessions).mockRejectedValue(new Error('gateway returned 503'))
    renderWithQueryClient(<AgentPanel />)

    await waitFor(() => expect(screen.getByText(/agents unavailable/i)).toBeInTheDocument())
    expect(screen.queryByText('no agents yet')).not.toBeInTheDocument()
  })

  it('surfaces a rejected detail fetch instead of leaking an unhandled promise', async () => {
    vi.mocked(gateway.fetchAgentStatus).mockRejectedValue(new Error('gateway returned 503'))
    renderWithQueryClient(<AgentPanel />)
    await waitFor(() => expect(screen.getByText('check the repo')).toBeInTheDocument())

    fireEvent.click(screen.getByText('check the repo'))

    await waitFor(() => expect(screen.getByText(/agent detail unavailable/i)).toBeInTheDocument())
    expect(screen.getByText(/gateway returned 503/i)).toBeInTheDocument()
  })
})
