import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ActivityCenter } from '../src/components/activity/ActivityCenter'

const projection = {
  items: [
    { id: 'action:7', source: 'action', source_id: '7', title: 'Approve calendar event', detail: 'Tomorrow at 10', state: 'waiting', raw_state: 'proposed', occurred_at: 40, destination: 'home' },
    { id: 'builder:kitty', source: 'builder', source_id: 'kitty', title: 'Kitty polish', detail: 'needs product decision', state: 'waiting', raw_state: 'paused', occurred_at: 35, destination: 'work' },
    { id: 'automation:1', source: 'automation', source_id: '1', title: 'brief.send', detail: 'Automation morning', state: 'running', raw_state: 'running', occurred_at: 30, destination: 'automations' },
    { id: 'agent:12', source: 'agent', source_id: '12', title: 'Compare implementations', detail: null, state: 'completed', raw_state: 'completed', occurred_at: 20, destination: 'agents' },
  ],
  counts: { total: 4, waiting: 2, running: 1, failed: 0, completed: 1 },
  sources: {
    actions: { state: 'available', reason: null },
    automations: { state: 'available', reason: null },
    agents: { state: 'available', reason: null },
    builder: { state: 'available', reason: null },
  },
} as const

afterEach(cleanup)

describe('ActivityCenter', () => {
  it('groups attention, running, and completed work and jumps to the owning surface', () => {
    const onNavigate = vi.fn()
    render(<ActivityCenter open projection={projection as any} isLoading={false} error={null} onClose={vi.fn()} onNavigate={onNavigate} />)

    const dialog = screen.getByRole('dialog', { name: /activity/i })
    expect(within(dialog).getByText('Needs you')).toBeVisible()
    expect(within(dialog).queryByText('live work', { exact: true })).not.toBeInTheDocument()
    expect(within(dialog).getByText('In motion')).toBeVisible()
    expect(within(dialog).getByText('Recently finished')).toBeVisible()
    expect(within(dialog).getByText('Approve calendar event')).toBeVisible()
    expect(within(dialog).getByText('Kitty polish')).toBeVisible()

    fireEvent.click(within(dialog).getByRole('button', { name: /open kitty polish/i }))
    expect(onNavigate).toHaveBeenCalledWith(expect.objectContaining({ source: 'builder', destination: 'work', source_id: 'kitty' }))
  })

  it('shows product-safe partial-source truth without leaking internal failure details', () => {
    render(<ActivityCenter
      open
      projection={{ ...projection, sources: { ...projection.sources, builder: { state: 'unavailable', reason: 'Builder queue database does not exist: /Users/jacob/private/builder_queue.db' } } } as any}
      isLoading={false}
      error={null}
      onClose={vi.fn()}
      onNavigate={vi.fn()}
    />)

    expect(screen.getByText(/some activity sources are unavailable/i)).toBeVisible()
    expect(screen.getByText(/work activity is temporarily unavailable/i)).toBeVisible()
    expect(screen.queryByText(/\/Users\/jacob/)).not.toBeInTheDocument()
    expect(screen.queryByText(/builder_queue\.db/)).not.toBeInTheDocument()
  })

  it('shows a refresh failure even when cached activity is still visible', () => {
    render(<ActivityCenter open projection={projection as any} isLoading={false} error={new Error('gateway offline')} onClose={vi.fn()} onNavigate={vi.fn()} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/activity may be out of date/i)
    expect(screen.getByText('Approve calendar event')).toBeVisible()
  })

  it('moves focus inside the modal while open', () => {
    const trigger = document.createElement('button')
    trigger.textContent = 'Activity trigger'
    document.body.appendChild(trigger)
    trigger.focus()
    render(<ActivityCenter open projection={projection as any} isLoading={false} error={null} onClose={vi.fn()} onNavigate={vi.fn()} />)
    expect(screen.getByRole('button', { name: /close activity/i })).toHaveFocus()
    trigger.remove()
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(<ActivityCenter open projection={projection as any} isLoading={false} error={null} onClose={onClose} onNavigate={vi.fn()} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
