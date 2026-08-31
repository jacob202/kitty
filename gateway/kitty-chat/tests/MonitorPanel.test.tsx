import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MonitorPanel } from '../src/components/MonitorPanel'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => ({
  ...(await vi.importActual<typeof queries>('../src/lib/queries')),
  useMonitors: vi.fn(), useAddMonitor: vi.fn(), useRemoveMonitor: vi.fn(),
}))

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MonitorPanel /></QueryClientProvider>)
}

describe('MonitorPanel', () => {
  beforeEach(() => {
    vi.mocked(queries.useMonitors).mockReturnValue({ data: [{ id: 'row-9', url: 'https://example.com', label: 'Example', last_keyword_matched: false }], isPending: false, isError: false } as never)
    vi.mocked(queries.useAddMonitor).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
    vi.mocked(queries.useRemoveMonitor).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
  })
  afterEach(cleanup)

  it('removes a backend-shaped monitor by its list-row id', async () => {
    const remove = vi.fn()
    vi.mocked(queries.useRemoveMonitor).mockReturnValue({ mutate: remove, isPending: false } as never)
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /remove/i }))
    await waitFor(() => expect(remove).toHaveBeenCalledWith('row-9'))
  })

  it('submits URL and label through the add mutation', () => {
    const add = vi.fn()
    vi.mocked(queries.useAddMonitor).mockReturnValue({ mutate: add, isPending: false } as never)
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /add monitor/i }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Monitor URL' }), { target: { value: 'https://kitty.dev' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Monitor label' }), { target: { value: 'Kitty' } })
    fireEvent.click(screen.getByRole('button', { name: 'add' }))
    expect(add).toHaveBeenCalledWith({ url: 'https://kitty.dev', label: 'Kitty' }, expect.any(Object))
  })

  it('renders the backend matched status field', () => {
    vi.mocked(queries.useMonitors).mockReturnValue({ data: [{ id: 'row-9', url: 'https://example.com', label: 'Example', last_keyword_matched: true }], isPending: false, isError: false } as never)
    renderPanel()
    expect(screen.getByText('hit')).toBeInTheDocument()
  })

  it('shows a friendly load failure and retries', () => {
    const refetch = vi.fn()
    vi.mocked(queries.useMonitors).mockReturnValue({ data: undefined, isPending: false, isError: true, refetch } as never)
    renderPanel()
    expect(screen.getByText(/monitors are unavailable/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /retry monitors/i }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('shows a friendly loading state', () => {
    vi.mocked(queries.useMonitors).mockReturnValue({ data: undefined, isPending: true, isError: false } as never)
    renderPanel()
    expect(screen.getByText('loading monitors…')).toBeInTheDocument()
  })

  it('shows friendly mutation failure status', () => {
    vi.mocked(queries.useRemoveMonitor).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: true } as never)
    renderPanel()
    expect(screen.getByText(/couldn't remove monitor/i)).toBeInTheDocument()
  })

  it('shows paused for disabled monitors', () => {
    vi.mocked(queries.useMonitors).mockReturnValue({
      data: [{ id: 'row-1', url: 'https://example.com', label: 'Example', last_keyword_matched: false, enabled: false }],
      isPending: false,
      isError: false,
    } as never)
    renderPanel()
    expect(screen.getByText('paused')).toBeInTheDocument()
  })

  it('shows watching for enabled monitors without keyword match', () => {
    vi.mocked(queries.useMonitors).mockReturnValue({
      data: [{ id: 'row-2', url: 'https://example.com', label: 'Example', last_keyword_matched: false, enabled: true }],
      isPending: false,
      isError: false,
    } as never)
    renderPanel()
    expect(screen.getByText('watching')).toBeInTheDocument()
  })

  it('shows hit for enabled monitors with keyword match', () => {
    vi.mocked(queries.useMonitors).mockReturnValue({
      data: [{ id: 'row-3', url: 'https://example.com', label: 'Example', last_keyword_matched: true, enabled: true }],
      isPending: false,
      isError: false,
    } as never)
    renderPanel()
    expect(screen.getByText('hit')).toBeInTheDocument()
  })

  it('defaults to watching when enabled field is missing', () => {
    vi.mocked(queries.useMonitors).mockReturnValue({
      data: [{ id: 'row-4', url: 'https://example.com', label: 'Example', last_keyword_matched: false }],
      isPending: false,
      isError: false,
    } as never)
    renderPanel()
    expect(screen.getByText('watching')).toBeInTheDocument()
  })

  it('disables remove button while mutation is pending', () => {
    vi.mocked(queries.useRemoveMonitor).mockReturnValue({ mutate: vi.fn(), isPending: true } as never)
    renderPanel()
    expect(screen.getByRole('button', { name: /remove/i })).toBeDisabled()
  })

  it('enables remove button when mutation is not pending', () => {
    vi.mocked(queries.useRemoveMonitor).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
    renderPanel()
    expect(screen.getByRole('button', { name: /remove/i })).not.toBeDisabled()
  })
})
