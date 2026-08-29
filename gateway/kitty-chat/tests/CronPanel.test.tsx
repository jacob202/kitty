import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest'
import { CronPanel } from '../src/components/CronPanel'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    fetchCronSchedules: vi.fn(),
    fetchCronActions: vi.fn(),
    createCronSchedule: vi.fn(),
    updateCronSchedule: vi.fn(),
    deleteCronSchedule: vi.fn(),
    toggleCronSchedule: vi.fn(),
    fetchScheduleWhy: vi.fn(),
    retryAutomationRun: vi.fn(),
  }
})

const mockSchedules: gateway.CronSchedule[] = [
  {
    id: 'abc123',
    name: 'Morning brief',
    action: 'brief.refresh',
    schedule_type: 'daily',
    schedule_value: '07:00',
    last_run: 0,
    enabled: 1,
  },
  {
    id: 'def456',
    name: 'Nudge check',
    action: 'nudges.check',
    schedule_type: 'interval',
    schedule_value: '30',
    last_run: 1700000000,
    enabled: 0,
  },
]

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

describe('CronPanel', () => {
  beforeEach(() => {
    vi.mocked(gateway.fetchCronSchedules).mockResolvedValue(mockSchedules)
    vi.mocked(gateway.fetchCronActions).mockResolvedValue(['brief.refresh', 'nudges.check'])
    vi.mocked(gateway.toggleCronSchedule).mockResolvedValue(true)
    vi.mocked(gateway.deleteCronSchedule).mockResolvedValue(true)
    vi.mocked(gateway.updateCronSchedule).mockResolvedValue(true)
    vi.mocked(gateway.createCronSchedule).mockResolvedValue('new-id')
    vi.mocked(gateway.fetchScheduleWhy).mockResolvedValue({
      status: 'not_yet_due',
      reason: 'next occurrence is not due yet',
      relevant_at: 1700000061,
      action: 'brief.refresh',
      automation: 'abc123',
      evidence: { next_due_at: 1700000061 },
      next_step: 'nothing to do; it will run when the next occurrence is due',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders schedules and active count', async () => {
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => {
      expect(screen.getByText('Morning brief')).toBeInTheDocument()
    })
    expect(screen.getByText('1/2 active')).toBeInTheDocument()
    expect(screen.getByText(/nudges\.check/)).toBeInTheDocument()
  })

  it('toggles a schedule', async () => {
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'disable schedule' }))
    await waitFor(() => {
      expect(gateway.toggleCronSchedule).toHaveBeenCalledWith('abc123')
    })
  })

  it('opens edit form and saves changes', async () => {
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    const editButtons = screen.getAllByRole('button', { name: 'edit schedule' })
    fireEvent.click(editButtons[0])
    const nameInput = screen.getByDisplayValue('Morning brief')
    fireEvent.change(nameInput, { target: { value: 'Evening brief' } })
    fireEvent.click(screen.getByRole('button', { name: 'update' }))

    await waitFor(() => {
      expect(gateway.updateCronSchedule).toHaveBeenCalledWith(
        'abc123',
        'Evening brief',
        'brief.refresh',
        'daily',
        '07:00',
      )
    })
  })

  it('creates a new schedule', async () => {
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText('+ add schedule')).toBeInTheDocument())

    fireEvent.click(screen.getByText('+ add schedule'))
    fireEvent.change(screen.getByPlaceholderText('name'), { target: { value: 'New job' } })
    fireEvent.click(screen.getByRole('button', { name: 'save' }))

    await waitFor(() => {
      expect(gateway.createCronSchedule).toHaveBeenCalledWith(
        'New job',
        'brief.refresh',
        'daily',
        '07:00',
      )
    })
  })

  it('shows empty state when no schedules', async () => {
    vi.mocked(gateway.fetchCronSchedules).mockResolvedValue([])
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => {
      expect(screen.getByText('no schedules yet')).toBeInTheDocument()
    })
    expect(screen.getByText('0/0 active')).toBeInTheDocument()
  })

  it('explains why a schedule did not run when the why button is clicked', async () => {
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    fireEvent.click(screen.getAllByRole('button', { name: 'why schedule' })[0])
    await waitFor(() => {
      expect(gateway.fetchScheduleWhy).toHaveBeenCalledWith('abc123')
      expect(screen.getByText('not yet due')).toBeInTheDocument()
    })
    expect(screen.getByText('next occurrence is not due yet')).toBeInTheDocument()
    expect(screen.getByText(/next: nothing to do/)).toBeInTheDocument()
  })

  it('collapses the explanation when the why button is clicked again', async () => {
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    const whyButtons = screen.getAllByRole('button', { name: 'why schedule' })
    fireEvent.click(whyButtons[0])
    await waitFor(() => expect(screen.getByText('not yet due')).toBeInTheDocument())

    fireEvent.click(screen.getAllByRole('button', { name: 'why schedule' })[0])
    await waitFor(() => {
      expect(screen.queryByText('not yet due')).not.toBeInTheDocument()
    })
  })

  it('surfaces the failure reason for a schedule that failed', async () => {
    vi.mocked(gateway.fetchScheduleWhy).mockResolvedValue({
      status: 'failed',
      reason: 'RuntimeError: boom',
      relevant_at: 1700000061,
      action: 'brief.refresh',
      automation: 'abc123',
      evidence: { run_id: 'arun_test' },
      next_step: 'check the run ledger for the full trace',
    })
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    fireEvent.click(screen.getAllByRole('button', { name: 'why schedule' })[0])
    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
    expect(screen.getByText('RuntimeError: boom')).toBeInTheDocument()
  })

  it('offers an explicit safe retry for a failed run and reports the fresh run id', async () => {
    vi.mocked(gateway.fetchScheduleWhy).mockResolvedValue({
      status: 'failed',
      reason: 'RuntimeError: boom',
      relevant_at: 1700000061,
      action: 'brief.refresh',
      automation: 'abc123',
      evidence: { run_id: 'arun_test' },
      next_step: 'review the failed run and retry it explicitly',
    })
    vi.mocked(gateway.retryAutomationRun).mockResolvedValue({
      run: { id: 'arun_retry', status: 'completed' },
      retried_from: 'arun_test',
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderWithQueryClient(<CronPanel variant="full" />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Why did Morning brief not run?' }))
    const retry = await screen.findByRole('button', { name: 'Retry failed run' })
    fireEvent.click(retry)

    await waitFor(() => {
      expect(confirm).toHaveBeenCalled()
      expect(gateway.retryAutomationRun).toHaveBeenCalledWith('arun_test')
      expect(screen.getByText('Retry completed as arun_retry.')).toBeVisible()
    })
  })

  it('presents full-size schedules in user language', async () => {
    renderWithQueryClient(<CronPanel variant="full" />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    expect(screen.getByText('Every day at 07:00')).toBeVisible()
    expect(screen.getByText('Kitty runs brief refresh')).toBeVisible()
    expect(screen.getByText('Active')).toBeVisible()
    expect(screen.getByText('Paused')).toBeVisible()
  })

  it('uses explicit touch-sized controls in the full automation surface', async () => {
    renderWithQueryClient(<CronPanel variant="full" />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeInTheDocument())

    expect(screen.getByRole('button', { name: 'Why did Morning brief not run?' })).toHaveStyle({ minHeight: '44px' })
    expect(screen.getByRole('button', { name: 'Pause Morning brief' })).toHaveStyle({ minHeight: '44px' })
    expect(screen.getByRole('button', { name: 'Edit Morning brief' })).toHaveStyle({ minHeight: '44px' })
  })

})

describe('CronPanel async truth', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('distinguishes schedule loading from an empty schedule list', () => {
    vi.mocked(gateway.fetchCronSchedules).mockReturnValue(new Promise(() => {}))
    vi.mocked(gateway.fetchCronActions).mockResolvedValue([])
    renderWithQueryClient(<CronPanel />)
    expect(screen.getByText(/loading schedules/i)).toBeVisible()
    expect(screen.queryByText(/no schedules yet/i)).not.toBeInTheDocument()
  })

  it('fails closed when schedules are unavailable instead of claiming none exist', async () => {
    vi.mocked(gateway.fetchCronSchedules).mockRejectedValue(new Error('offline'))
    vi.mocked(gateway.fetchCronActions).mockResolvedValue([])
    renderWithQueryClient(<CronPanel />)
    await waitFor(() => expect(screen.getByText(/schedules are unavailable right now/i)).toBeVisible())
    expect(screen.queryByText(/no schedules yet/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry schedules/i })).toBeVisible()
  })
})

describe('CronPanel mobile full layout', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('uses one shared schedule surface and a full-width mobile action row', async () => {
    vi.mocked(gateway.fetchCronSchedules).mockResolvedValue(mockSchedules)
    vi.mocked(gateway.fetchCronActions).mockResolvedValue(['brief.refresh', 'nudges.check'])
    renderWithQueryClient(<CronPanel variant="full" isMobile />)
    await waitFor(() => expect(screen.getByText('Morning brief')).toBeVisible())

    expect(screen.getByTestId('automation-schedule-list')).toBeVisible()
    expect(screen.getAllByTestId('automation-schedule-row')).toHaveLength(2)
    expect(screen.getAllByTestId('automation-schedule-actions')[0]).toHaveStyle({
      gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    })
  })
})
