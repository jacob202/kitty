import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest'
import { DreamStatus } from '../src/components/DreamStatus'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    fetchDreamStatus: vi.fn(),
    triggerDreamConsolidation: vi.fn(),
  }
})

describe('DreamStatus', () => {
  beforeEach(() => {
    vi.mocked(gateway.fetchDreamStatus).mockResolvedValue({
      status: 'idle',
      last_run: 1700000000,
      last_run_label: '2026-05-20T03:00:00',
      next_run: null,
      insights_count: 3,
      never: false,
    })
    vi.mocked(gateway.triggerDreamConsolidation).mockResolvedValue(true)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders dream loop status', async () => {
    render(<DreamStatus />)
    // The heading renders before fetchDreamStatus resolves, so waiting on it
    // raced the async state update under full-suite load.
    expect(await screen.findByText('3 insights')).toBeInTheDocument()
    expect(screen.getByText('2026-05-20T03:00:00')).toBeInTheDocument()
  })

  it('triggers consolidation', async () => {
    render(<DreamStatus />)
    await waitFor(() => expect(screen.getByText('run consolidation')).toBeInTheDocument())

    fireEvent.click(screen.getByText('run consolidation'))
    await waitFor(() => {
      expect(gateway.triggerDreamConsolidation).toHaveBeenCalled()
    })
  })

  it('shows never run state', async () => {
    vi.mocked(gateway.fetchDreamStatus).mockResolvedValue({
      status: 'never_run',
      last_run: null,
      next_run: null,
      insights_count: 0,
      never: true,
    })
    render(<DreamStatus />)
    await waitFor(() => {
      expect(screen.getByText('never run')).toBeInTheDocument()
    })
  })
})
