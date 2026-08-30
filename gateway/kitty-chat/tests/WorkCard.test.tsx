import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WorkCard } from '../src/components/shared/WorkCard'

afterEach(cleanup)

describe('WorkCard', () => {
  it('renders title and status', () => {
    render(<WorkCard id="1" title="Generate sunset image" status="working" statusDetail="step 2/4: denoising" />)
    expect(screen.getByText('Generate sunset image')).toBeDefined()
    expect(screen.getByText('working')).toBeDefined()
  })

  it('renders source chat link when provided', () => {
    render(<WorkCard id="1" title="Task" status="completed" sourceTitle="chat about images" sourceChatId="chat-1" />)
    expect(screen.getByText('chat about images')).toBeDefined()
  })

  it('renders progress bar when working with progress', () => {
    render(<WorkCard id="1" title="Task" status="working" progress={45} />)
    expect(screen.getByText('45%')).toBeDefined()
  })

  it('does not render progress when undefined', () => {
    render(<WorkCard id="1" title="Task" status="working" />)
    expect(screen.queryByText('0%')).toBeNull()
  })

  it('renders status detail text', () => {
    render(<WorkCard id="1" title="Task" status="failed" statusDetail="connection refused" />)
    expect(screen.getByText('connection refused')).toBeDefined()
  })

  it('renders artifact badges', () => {
    render(<WorkCard
      id="1"
      title="Task"
      status="completed"
      artifacts={[
        { type: 'image', title: 'sunset.png' },
        { type: 'document', title: 'notes.md' },
      ]}
    />)
    expect(screen.getByText('[IMG] sunset.png')).toBeDefined()
    expect(screen.getByText('[DOC] notes.md')).toBeDefined()
  })

  it('truncates artifacts to 4 with +N', () => {
    const artifacts = Array.from({ length: 6 }, (_, i) => ({ type: 'code' as const, title: `file-${i}.ts` }))
    render(<WorkCard id="1" title="Task" status="completed" artifacts={artifacts} />)
    expect(screen.getByText('+2')).toBeDefined()
  })

  it('renders action buttons', () => {
    const onRetry = vi.fn()
    const onResume = vi.fn()
    const onCancel = vi.fn()
    render(<WorkCard id="1" title="Task" status="failed" onRetry={onRetry} onResume={onResume} onCancel={onCancel} statusDetail="error" />)
    fireEvent.click(screen.getByText('retry'))
    expect(onRetry).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('resume'))
    expect(onResume).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('renders all status variants', () => {
    const states = ['working', 'needs_user', 'scheduled', 'paused', 'failed', 'completed', 'unavailable', 'degraded', 'canceled'] as const
    for (const status of states) {
      const { unmount } = render(<WorkCard id={status} title="test" status={status} />)
      const expectedLabel = {
        working: 'working', needs_user: 'needs you', scheduled: 'scheduled', paused: 'paused',
        failed: 'failed', completed: 'done', unavailable: 'offline', degraded: 'limited', canceled: 'canceled',
      }[status]
      expect(screen.getByText(expectedLabel)).toBeDefined()
      unmount()
    }
  })

  it('has correct role and aria-label', () => {
    render(<WorkCard id="1" title="My Task" status="needs_user" />)
    expect(screen.getByRole('status', { name: 'My Task: needs you' })).toBeDefined()
  })
})
