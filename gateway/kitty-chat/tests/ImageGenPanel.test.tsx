import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest'
import { ImageGenPanel } from '../src/components/ImageGenPanel'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    fetchImageStatus: vi.fn(),
    fetchImageHistory: vi.fn(),
    generateImage: vi.fn(),
  }
})

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

describe('ImageGenPanel', () => {
  beforeEach(() => {
    vi.mocked(gateway.fetchImageStatus).mockResolvedValue({ available: true })
    vi.mocked(gateway.fetchImageHistory).mockResolvedValue([])
    vi.mocked(gateway.generateImage).mockResolvedValue({ filename: 'Kitty_00001_.png' })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows offline state when ComfyUI unavailable', async () => {
    vi.mocked(gateway.fetchImageStatus).mockResolvedValue({ available: false })
    renderWithQueryClient(<ImageGenPanel />)
    await waitFor(() => {
      expect(screen.getByText('ComfyUI offline')).toBeInTheDocument()
    })
  })

  it('renders prompt input when available', async () => {
    renderWithQueryClient(<ImageGenPanel />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('describe the image…')).toBeInTheDocument()
      expect(screen.getByText('comfyui online')).toBeInTheDocument()
    })
  })

  it('submits generation request', async () => {
    renderWithQueryClient(<ImageGenPanel />)
    await waitFor(() => expect(screen.getByPlaceholderText('describe the image…')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText('describe the image…'), {
      target: { value: 'a cat in space' },
    })
    fireEvent.click(screen.getByText('generate'))

    await waitFor(() => {
      expect(gateway.generateImage).toHaveBeenCalledWith('a cat in space')
    })
  })
})
