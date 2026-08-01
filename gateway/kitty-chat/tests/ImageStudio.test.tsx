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

function errorStatus() {
  // Gateway / image-status endpoint unreachable — a DIFFERENT failure than
  // renderers being offline (PR #355 review finding 2).
  return {
    data: undefined,
    isPending: false,
    isError: true,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    error: new Error('Gateway returned 503 Service Unavailable'),
  }
}

function onlineStatus() {
  return {
    data: {
      available: true,
      backend: 'comfyui',
      engines: [{ name: 'comfyui', label: 'ComfyUI', available: true }],
    },
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

/** Stub global fetch for Studio routes; route generation to a raw HTML error to
 *  exercise finding 4. */
function stubStudioFetch(generateResponse?: unknown) {
  const mock = vi.fn(async (url: string, _init?: unknown) => {
    if (String(url).includes('/proxy/studio/generate')) {
      if (generateResponse) return generateResponse
      return { ok: true, status: 200, json: async () => ({ job_id: 'job_1', filename: 'cat.png' }) }
    }
    if (String(url).includes('/proxy/studio/characters')) {
      return { ok: true, status: 200, json: async () => ({ characters: [] }) }
    }
    if (String(url).includes('/proxy/studio/recipes')) {
      return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
    }
    return { ok: true, status: 200, json: async () => ({ available_guidance_tags: [] }) }
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

describe('ImageStudio fail-closed and renderer distinction (PR#355 findings 2-4)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  describe('renderers offline but gateway reachable (finding 3)', () => {
    beforeEach(() => {
      vi.mocked(queries.useImageStatus).mockReturnValue(offlineStatus() as never)
    })

    it('keeps the editor visible with generation disabled and a clear recovery', async () => {
      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByTestId('studio-offline')).toBeInTheDocument())

      // Renderer-independent surface stays usable.
      expect(screen.getByText(/no image engine is online/i)).toBeInTheDocument()
      expect(screen.getByTestId('studio-check-again')).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/describe what you want to create/i)).toBeInTheDocument()

      // Generation is present but disabled — not removed, never dispatched.
      const generate = screen.getByRole('button', { name: 'generate', exact: true })
      expect(generate).toBeDisabled()

      // Plan preview remains available offline (finding 3). With a prompt entered,
      // the button is clickable even while engines are down.
      fireEvent.change(screen.getByPlaceholderText(/describe what you want to create/i), {
        target: { value: 'a sleeping cat' },
      })
      const plan = screen.getByRole('button', { name: 'preview plan', exact: true })
      expect(plan).not.toBeDisabled()

      // check again re-checks status rather than dispatching generation.
      const refetch = vi.mocked(queries.useImageStatus).mock.results[0]?.value?.refetch
      fireEvent.click(screen.getByTestId('studio-check-again'))
      expect(refetch).toHaveBeenCalled()
    })

    it('plan preview stays enabled and dispatches the planning route while offline', async () => {
      const fetchMock = stubStudioFetch()
      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByTestId('studio-offline')).toBeInTheDocument())

      const input = screen.getByPlaceholderText(/describe what you want to create/i)
      fireEvent.change(input, { target: { value: 'a sleeping cat' } })
      fireEvent.click(screen.getByRole('button', { name: 'preview plan', exact: true }))

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/proxy/studio/plan'),
          expect.objectContaining({ method: 'POST' }),
        )
      })
    })
  })

  describe('gateway unreachable (finding 2)', () => {
    it('shows the gateway failure state, not "start ComfyUI"', async () => {
      vi.mocked(queries.useImageStatus).mockReturnValue(errorStatus() as never)
      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByTestId('studio-status-error')).toBeInTheDocument())

      expect(screen.getByText(/can’t reach the image service/i)).toBeInTheDocument()
      expect(screen.getByText(/check that kitty’s gateway is running/i)).toBeInTheDocument()
      // Must NOT tell the user to start renderers when the failure is the gateway.
      expect(screen.queryByText(/start ComfyUI or Draw Things/i)).not.toBeInTheDocument()
      expect(screen.getByTestId('studio-check-again')).toBeInTheDocument()
    })
  })

  describe('raw HTML error document (finding 4)', () => {
    it('renders a human message with the <!DOCTYPE html> page as technical detail', async () => {
      vi.mocked(queries.useImageStatus).mockReturnValue(onlineStatus() as never)
      stubStudioFetch({
        ok: false,
        status: 500,
        text: async () => '<!DOCTYPE html><html><body><h1>Internal Server Error</h1></body></html>',
      })

      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByPlaceholderText(/describe what you want to create/i)).toBeInTheDocument())

      fireEvent.change(screen.getByPlaceholderText(/describe what you want to create/i), {
        target: { value: 'a cat' },
      })
      fireEvent.click(screen.getByRole('button', { name: 'generate', exact: true }))

      // Primary message is human, not the raw HTML page.
      await waitFor(() => {
        expect(screen.getByText(/internal error — check your renderer/i)).toBeInTheDocument()
      })
      expect(screen.getByText('technical detail')).toBeInTheDocument()
      expect(screen.getByText(/<!doctype html>/i)).toBeInTheDocument()
    })
  })
})
