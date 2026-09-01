import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AgentSessionsPanel } from '../src/components/AgentSessionsPanel'
import { useAgentSessions, useAgentStatus, useStopAgent } from '../src/lib/queries'

vi.mock('../src/lib/queries', () => ({
  useAgentSessions: vi.fn(),
  useAgentStatus: vi.fn(),
  useStopAgent: vi.fn(),
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AgentSessionsPanel', () => {
  it('renders the exact selected autonomous session instead of shared workspace data', () => {
    ;(useAgentStatus as any).mockReturnValue({ data: { session_id: 42, goal: 'Investigate billing', status: 'failed', iterations: 3, output: 'Provider rejected the final request.' }, isLoading: false, isError: false })
    ;(useAgentSessions as any).mockReturnValue({ data: [], isLoading: false, isError: false })
    ;(useStopAgent as any).mockReturnValue({ mutate: vi.fn(), isPending: false })

    render(<AgentSessionsPanel selectedSessionId={42} />)

    expect(screen.getByRole('article', { name: 'Agent session 42' })).toHaveTextContent('Investigate billing')
    expect(screen.getByText('Provider rejected the final request.')).toBeVisible()
    expect(screen.queryByRole('button', { name: /stop agent/i })).not.toBeInTheDocument()
  })

  it('offers stop only for the selected active session', () => {
    const mutate = vi.fn()
    ;(useAgentStatus as any).mockReturnValue({ data: { session_id: 9, goal: 'Still researching', status: 'active', iterations: 1, last_output_snippet: 'Reading sources…' }, isLoading: false, isError: false })
    ;(useAgentSessions as any).mockReturnValue({ data: [], isLoading: false, isError: false })
    ;(useStopAgent as any).mockReturnValue({ mutate, isPending: false })

    render(<AgentSessionsPanel selectedSessionId={9} />)
    fireEvent.click(screen.getByRole('button', { name: /stop agent/i }))
    expect(mutate).toHaveBeenCalledWith(9)
  })
})
