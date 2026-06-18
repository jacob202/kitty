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
})
