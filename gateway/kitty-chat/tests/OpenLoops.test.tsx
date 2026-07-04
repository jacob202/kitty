import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { OpenLoops } from '../src/components/OpenLoops'

describe('OpenLoops', () => {
  afterEach(cleanup)

  it('renders each count as a clickable verb, not a bare number', () => {
    const onRunTriage = vi.fn()
    const onJumpToNeedsYou = vi.fn()
    render(
      <OpenLoops
        untriagedCount={4}
        proposedCount={2}
        needsJacobCount={1}
        onRunTriage={onRunTriage}
        onJumpToNeedsYou={onJumpToNeedsYou}
      />
    )

    fireEvent.click(screen.getByText(/4 untriaged/))
    expect(onRunTriage).toHaveBeenCalled()

    fireEvent.click(screen.getByText(/2 proposed actions/))
    expect(onJumpToNeedsYou).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText(/1 needs a decision/))
    expect(onJumpToNeedsYou).toHaveBeenCalledTimes(2)
  })

  it('disables actions with nothing behind them', () => {
    render(
      <OpenLoops
        untriagedCount={0}
        proposedCount={0}
        needsJacobCount={0}
        onRunTriage={() => {}}
        onJumpToNeedsYou={() => {}}
      />
    )
    expect(screen.getByText(/0 untriaged/)).toBeDisabled()
    expect(screen.getByText(/0 proposed action/)).toBeDisabled()
  })
})
