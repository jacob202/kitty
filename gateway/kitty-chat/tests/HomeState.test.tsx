import { render, screen, cleanup } from '@testing-library/react'
import { describe, expect, it, afterEach } from 'vitest'
import { HomeState } from '../src/components/HomeState'

describe('HomeState', () => {
  afterEach(cleanup)

  const baseProps = {
    brief: null,
    todos: [],
    todayError: null,
    proposedActions: [],
    proposedActionsError: null,
    needsJacob: [],
    needsJacobError: null,
    stateChanges: [],
    newSignals: [],
    hasBaseline: false,
    stateChangesError: null,
    onSnapshot: () => {},
    untriagedCount: 0,
    onRunTriage: () => {},
    onApproveAction: () => {},
    onRejectAction: () => {},
    onPromptSelect: () => {},
  }

  it('renders every section named in packet 004 exact scope', () => {
    render(<HomeState {...baseProps} />)
    expect(screen.getByText('Needs you')).toBeInTheDocument()
    expect(screen.getByText('What changed')).toBeInTheDocument()
    expect(screen.getByText('open loops')).toBeInTheDocument()
    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('DROP FILE OR CLICK TO CAPTURE')).toBeInTheDocument()
  })

  it('shows honest empty states with the gateway up but no data — no fabricated rows', () => {
    render(<HomeState {...baseProps} />)
    expect(screen.getByText('Nothing needs you right now.')).toBeInTheDocument()
    expect(screen.getByText('No priority items for today')).toBeInTheDocument()
  })

  it('shows honest error states with the gateway down, not spinners-forever', () => {
    render(
      <HomeState
        {...baseProps}
        todayError="Could not reach the gateway"
        proposedActionsError="Could not reach the gateway"
        needsJacobError="Could not reach the gateway"
        stateChangesError="Could not reach the gateway"
      />
    )
    const alerts = screen.getAllByRole('alert')
    expect(alerts.length).toBeGreaterThan(0)
    expect(screen.queryByText('Nothing needs you right now.')).not.toBeInTheDocument()
    expect(screen.queryByText('No priority items for today')).not.toBeInTheDocument()
  })
})
