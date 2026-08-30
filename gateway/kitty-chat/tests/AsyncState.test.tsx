import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AsyncState } from '../src/components/ui/AsyncState'

afterEach(cleanup)

describe('AsyncState', () => {
  it('renders loading state', () => {
    render(<AsyncState state="loading" />)
    expect(screen.getByText('Loading…')).toBeDefined()
    expect(screen.getByRole('status')).toBeDefined()
  })

  it('renders empty state', () => {
    render(<AsyncState state="empty" />)
    expect(screen.getByText('Nothing here yet')).toBeDefined()
  })

  it('renders error state with retry button', () => {
    const onRetry = vi.fn()
    render(<AsyncState state="error" onRetry={onRetry} />)
    expect(screen.getByText('Something went wrong')).toBeDefined()
    fireEvent.click(screen.getByText('retry'))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders unavailable state with reconnect button', () => {
    const onReconnect = vi.fn()
    render(<AsyncState state="unavailable" onReconnect={onReconnect} />)
    expect(screen.getByText('Unavailable')).toBeDefined()
    fireEvent.click(screen.getByText('reconnect'))
    expect(onReconnect).toHaveBeenCalledTimes(1)
  })

  it('renders custom title and message', () => {
    render(<AsyncState state="error" title="Custom error" message="Something custom failed" />)
    expect(screen.getByText('Custom error')).toBeDefined()
    expect(screen.getByText('Something custom failed')).toBeDefined()
  })

  it('renders all states', () => {
    const states: Array<AsyncState['state']> = [
      'loading', 'empty', 'degraded', 'unavailable', 'stale', 'error', 'retrying', 'partial', 'forbidden'
    ]
    const labels = [
      'Loading…', 'Nothing here yet', 'Running with limited capability', 'Unavailable',
      'Showing cached data', 'Something went wrong', 'Retrying…', 'Partial results', 'Permission needed'
    ]
    for (let i = 0; i < states.length; i++) {
      const { unmount } = render(<AsyncState state={states[i]} />)
      expect(screen.getByText(labels[i])).toBeDefined()
      unmount()
    }
  })
})

