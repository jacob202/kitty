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
    vi.mocked(queries.useMonitors).mockReturnValue({ data: [{ id: 'row-9', url: 'https://example.com', label: 'Example', last_match: null }], isPending: false } as never)
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
    fireEvent.change(screen.getByPlaceholderText('https://…'), { target: { value: 'https://kitty.dev' } })
    fireEvent.change(screen.getByPlaceholderText('label (optional)'), { target: { value: 'Kitty' } })
    fireEvent.click(screen.getByRole('button', { name: 'add' }))
    expect(add).toHaveBeenCalledWith({ url: 'https://kitty.dev', label: 'Kitty' }, expect.any(Object))
  })
})
