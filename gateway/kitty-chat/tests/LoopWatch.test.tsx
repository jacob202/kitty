import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { LoopWatch } from '../src/components/LoopWatch'
import type { GatewayLoop } from '../src/lib/gateway'

describe('LoopWatch', () => {
  afterEach(cleanup)

  const mockLoops: GatewayLoop[] = [
    {
      loop_id: 'loop-1',
      name: 'Daily Brief',
      description: 'Generates morning brief',
      status: 'running',
      interval_minutes: 60,
      last_run: Date.now() - 1000 * 60 * 5,
    },
    {
      loop_id: 'loop-2',
      name: 'Search Index',
      description: 'Updates search index',
      status: 'paused',
      interval_minutes: 15,
    },
    {
      loop_id: 'loop-3',
      name: 'Backup',
      status: 'idle',
    },
  ]

  it('renders loop watch title and count', () => {
    render(<LoopWatch loops={mockLoops} />)
    expect(screen.getByText('Loop Watch')).toBeInTheDocument()
    expect(screen.getByText('1 running · 3 total')).toBeInTheDocument()
  })

  it('shows all loops with correct statuses', () => {
    render(<LoopWatch loops={mockLoops} />)
    expect(screen.getByText('Daily Brief')).toBeInTheDocument()
    expect(screen.getByText('RUNNING')).toBeInTheDocument()
    expect(screen.getByText('Search Index')).toBeInTheDocument()
    expect(screen.getByText('PAUSED')).toBeInTheDocument()
    expect(screen.getByText('Backup')).toBeInTheDocument()
    expect(screen.getByText('IDLE')).toBeInTheDocument()
  })

  it('shows empty state when no loops', () => {
    render(<LoopWatch loops={[]} />)
    expect(screen.getByText('no loops configured')).toBeInTheDocument()
  })

  it('calls onToggle when toggle button clicked', () => {
    const onToggle = vi.fn()
    render(<LoopWatch loops={mockLoops} onToggle={onToggle} />)

    const toggleButtons = screen.getAllByRole('button', { name: /^(start loop|pause loop)$/i })
    expect(toggleButtons.length).toBeGreaterThan(0)

    fireEvent.click(toggleButtons[0])
    expect(onToggle).toHaveBeenCalledWith('loop-1')
  })

  it('does not show toggle button for error status loops', () => {
    const errorLoop: GatewayLoop = {
      loop_id: 'loop-error',
      name: 'Broken Loop',
      status: 'error',
      error_message: 'Something broke',
    }
    render(<LoopWatch loops={[errorLoop]} />)
    expect(screen.getByText('ERROR')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^(start|pause)/i })).not.toBeInTheDocument()
  })

  it('shows last run time when available', () => {
    render(<LoopWatch loops={mockLoops} />)
    // The "Last run:" text should appear at least once
    expect(screen.getAllByText(/last run:/).length).toBeGreaterThan(0)
  })

  it('displays custom title', () => {
    render(<LoopWatch loops={mockLoops} title="Active Loops" />)
    expect(screen.getByText('Active Loops')).toBeInTheDocument()
  })
})

describe('LoopWatch presentation', () => {
  const presentationLoops: GatewayLoop[] = [
    { loop_id: 'loop-1', name: 'Daily Brief', status: 'running', interval_minutes: 60 },
    { loop_id: 'loop-2', name: 'Search Index', status: 'paused', interval_minutes: 15 },
    { loop_id: 'loop-3', name: 'Backup', status: 'idle' },
  ]

  afterEach(cleanup)

  it('reports running versus total routines truthfully', () => {
    render(<LoopWatch loops={presentationLoops} />)
    expect(screen.getByText('1 running · 3 total')).toBeVisible()
  })

  it('uses one shared routine list and touch-sized toggles', () => {
    render(<LoopWatch loops={presentationLoops} onToggle={vi.fn()} />)
    expect(screen.getByTestId('automation-loop-list')).toBeVisible()
    expect(screen.getAllByTestId('automation-loop-row')).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'pause loop' })).toHaveStyle({ minHeight: '44px' })
  })
})
