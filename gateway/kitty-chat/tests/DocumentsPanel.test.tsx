import { render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest'
import { DocumentsPanel } from '../src/components/DocumentsPanel'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useKnowledgeSources: vi.fn(),
    useKnowledgeSearch: vi.fn(),
    useIngestKnowledge: vi.fn(),
    useUploadCapture: vi.fn(),
  }
})

function renderPanel(isMobile: boolean) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <DocumentsPanel isMobile={isMobile} />
    </QueryClientProvider>,
  )
}

describe('DocumentsPanel mobile (#346 Slice 1, PR#355 finding 1)', () => {
  beforeEach(() => {
    vi.mocked(queries.useKnowledgeSources).mockReturnValue({
      data: { total_sources: 0, total_chunks: 0, sources: [] },
      isPending: false, isFetching: false, isLoading: false, isError: false,
      refetch: vi.fn(),
    } as never)
    vi.mocked(queries.useKnowledgeSearch).mockReturnValue({
      data: undefined, isPending: false, isError: false, isLoading: false,
    } as never)
    vi.mocked(queries.useUploadCapture).mockReturnValue({
      isPending: false, isError: false, isSuccess: false, data: undefined, error: null, mutate: vi.fn(),
    } as never)
  })

  afterEach(cleanup)

  it('hides the Mac-path affordance on mobile but KEEPS a URL ingestion control', () => {
    vi.mocked(queries.useIngestKnowledge).mockReturnValue({
      isPending: false, isError: false, data: undefined, error: null, mutate: vi.fn(),
    } as never)
    renderPanel(true)

    expect(screen.queryByTestId('library-path-control')).not.toBeInTheDocument()
    expect(screen.queryByText(/file path on the Mac/i)).not.toBeInTheDocument()
    expect(screen.getByTestId('library-url-control')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/paste a URL/i)).toBeInTheDocument()
    expect(screen.getByTestId('library-file-picker')).toBeInTheDocument()
    expect(document.querySelector('input[type="file"][accept*=".pdf"]')).not.toBeNull()
  })

  it('keeps ingest error state visible on mobile (not hidden behind desktop-only)', () => {
    vi.mocked(queries.useIngestKnowledge).mockReturnValue({
      isPending: false, isError: true, data: undefined,
      error: new Error('gateway exploded'), mutate: vi.fn(),
    } as never)
    renderPanel(true)
    expect(screen.getByText(/ingest failed — gateway exploded/i)).toBeInTheDocument()
    expect(screen.getByTestId('library-url-control')).toBeInTheDocument()
  })

  it('keeps ingest result state visible on mobile', () => {
    vi.mocked(queries.useIngestKnowledge).mockReturnValue({
      isPending: false, isError: false,
      data: { status: 'success', source_id: 'doc-1', reason: 'indexed 12 chunks' },
      error: null, mutate: vi.fn(),
    } as never)
    renderPanel(true)
    expect(screen.getByText('indexed')).toBeInTheDocument()
    expect(screen.getByText('doc-1')).toBeInTheDocument()
    expect(screen.getByText('indexed 12 chunks')).toBeInTheDocument()
  })

  it('keeps the full path/URL control on desktop', () => {
    vi.mocked(queries.useIngestKnowledge).mockReturnValue({
      isPending: false, isError: false, data: undefined, error: null, mutate: vi.fn(),
    } as never)
    renderPanel(false)
    expect(screen.getByTestId('library-path-control')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/a file path on the Mac, or a URL/i)).toBeInTheDocument()
    expect(screen.getByTestId('library-file-picker')).toBeInTheDocument()
  })
})
