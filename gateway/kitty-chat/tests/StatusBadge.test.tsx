import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { StatusBadge } from '../src/components/ui/StatusBadge'

afterEach(cleanup)

describe('StatusBadge', () => {
  it('renders all states with correct labels', () => {
    const states = ['working', 'needs_user', 'scheduled', 'paused', 'failed', 'completed', 'unavailable', 'degraded', 'canceled'] as const
    const expected = {
      working: 'working', needs_user: 'needs you', scheduled: 'scheduled', paused: 'paused',
      failed: 'failed', completed: 'done', unavailable: 'offline', degraded: 'limited', canceled: 'canceled',
    }
    for (const state of states) {
      const { unmount } = render(<StatusBadge state={state} />)
      expect(screen.getByText(expected[state])).toBeDefined()
      unmount()
    }
  })

  it('renders as dot variant without label text', () => {
    render(<StatusBadge state="working" variant="dot" />)
    expect(screen.getByRole('status')).toBeDefined()
    expect(screen.queryByText('working')).toBeNull()
  })

  it('renders with custom label override', () => {
    render(<StatusBadge state="needs_user" label="action required" />)
    expect(screen.getByText('action required')).toBeDefined()
  })

  it('compact mode renders as dot', () => {
    render(<StatusBadge state="failed" compact />)
    expect(screen.getByRole('status')).toBeDefined()
    expect(screen.queryByText('failed')).toBeNull()
  })

  it('has role="status" for accessibility', () => {
    render(<StatusBadge state="completed" />)
    expect(screen.getByRole('status')).toBeDefined()
  })
})
