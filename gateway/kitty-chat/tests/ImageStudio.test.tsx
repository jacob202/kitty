import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest'
import { ImageStudio } from '../src/components/ImageStudio'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useImageStatus: vi.fn(),
  }
})

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

function offlineStatus() {
  return {
    data: {
      available: false,
      backend: 'comfyui',
      engines: [
        { name: 'comfyui', label: 'ComfyUI', available: false },
        { name: 'drawthings', label: 'Draw Things', available: false },
      ],
    },
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

describe('ImageStudio fail-closed (#346 Slice 1)', () => {
  beforeEach(() => {
    vi.mocked(queries.useImageStatus).mockReturnValue(offlineStatus() as never)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders a single unavailable state with a check-again action when no engine is online', async () => {
    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => {
      expect(screen.getByTestId('studio-offline')).toBeInTheDocument()
    })
    expect(screen.getByText('image engines offline')).toBeInTheDocument()
    expect(screen.getByTestId('studio-check-again')).toBeInTheDocument()
    // No live-looking generation surface may exist while engines are offline.
    expect(screen.queryByPlaceholderText(/describe what you want to create/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'generate', exact: true })).not.toBeInTheDocument()
  })

  it('check again refetches engine status instead of dispatching a request', async () => {
    const refetch = vi.fn().mockResolvedValue(undefined)
    vi.mocked(queries.useImageStatus).mockReturnValue({ ...offlineStatus(), refetch } as never)
    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-check-again')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('studio-check-again'))
    expect(refetch).toHaveBeenCalled()
  })
})
