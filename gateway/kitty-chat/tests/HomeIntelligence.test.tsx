import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HomeIntelligence } from '../src/components/HomeIntelligence'

const projection = {
  items: [
    { id: 'deadline:12', source: 'deadline', title: 'Renew registration', detail: 'Due 2026-09-01 · needs your confirmation', destination: 'projects', project_id: 7, prompt: 'Help me handle this deadline: Renew registration' },
    { id: 'magic:1', source: 'magic', title: 'Two projects overlap', detail: 'Reuse the artifact flow.', destination: 'chat', project_id: null, prompt: 'Explore this cross-project connection with me.' },
    { id: 'insight:9', source: 'insight', title: 'Revisit the provider decision', detail: 'Returned decision', destination: 'chat', project_id: null, prompt: 'Help me act on this returned insight.' },
  ],
  counts: { shown: 3, total_candidates: 5 },
  sources: {
    deadline: { state: 'available', reason: null }, insight: { state: 'available', reason: null },
    magic: { state: 'available', reason: null }, life: { state: 'available', reason: null },
  },
}

describe('HomeIntelligence', () => {
  afterEach(cleanup)

  it('renders one selective Kitty noticed surface with at most three ranked notices', () => {
    render(<HomeIntelligence projection={projection} />)
    expect(screen.getByRole('region', { name: 'Kitty noticed' })).toBeInTheDocument()
    expect(screen.getByText('Renew registration')).toBeInTheDocument()
    expect(screen.getByText('Two projects overlap')).toBeInTheDocument()
    expect(screen.getByText('Revisit the provider decision')).toBeInTheDocument()
    expect(screen.getAllByTestId('kitty-notice')).toHaveLength(3)
  })

  it('opens the owning project or moves a notice into Chat', () => {
    const onOpenProject = vi.fn()
    const onDiscuss = vi.fn()
    render(<HomeIntelligence projection={projection} onOpenProject={onOpenProject} onDiscuss={onDiscuss} />)

    fireEvent.click(screen.getByRole('button', { name: 'Open project for Renew registration' }))
    expect(onOpenProject).toHaveBeenCalledWith(7)

    fireEvent.click(screen.getByRole('button', { name: 'Talk to Kitty about Two projects overlap' }))
    expect(onDiscuss).toHaveBeenCalledWith('Explore this cross-project connection with me.')
  })

  it('stays out of the way when there is nothing meaningful to show', () => {
    render(<HomeIntelligence projection={{ ...projection, items: [], counts: { shown: 0, total_candidates: 0 } }} />)
    expect(screen.queryByRole('region', { name: 'Kitty noticed' })).not.toBeInTheDocument()
  })
})
