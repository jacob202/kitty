import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LibraryView from '../src/components/LibraryView'

vi.mock('../src/components/DocumentsPanel', () => ({
  DocumentsPanel: () => <div>knowledge unavailable — retry indexing</div>,
}))

function renderLibrary(isMobile = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <LibraryView isMobile={isMobile} />
    </QueryClientProvider>,
  )
}

describe('LibraryView artifact truth', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/proxy/artifacts')) {
        return new Response(JSON.stringify({
          artifacts: [{
            id: 'artifact_1',
            project_id: 7,
            kind: 'capture',
            media_type: 'image/png',
            display_name: 'camera-reference.png',
            state: 'ready',
            size_bytes: 2048,
            created_at: 1787259000,
            created_by: 'capture',
            conversation_id: 'chat-1',
            metadata: { ingestion_status: 'queued' },
            error: null,
          }],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('not found', { status: 404 })
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('shows canonical artifacts even when the knowledge index is degraded', async () => {
    renderLibrary()

    expect(await screen.findByText('camera-reference.png')).toBeInTheDocument()
    expect(screen.getByText(/image\/png/i)).toBeInTheDocument()
    expect(screen.getByText(/project 7/i)).toBeInTheDocument()
    expect(screen.getByText(/conversation chat-1/i)).toBeInTheDocument()
    expect(screen.getByText(/knowledge unavailable/i)).toBeInTheDocument()
  })

  it('keeps the knowledge index visible when artifact listing fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('offline', { status: 503 })))
    renderLibrary()

    expect(await screen.findByText(/couldn't read saved files/i)).toBeInTheDocument()
    expect(screen.getByText(/knowledge unavailable/i)).toBeInTheDocument()
  })
})
