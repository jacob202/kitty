import { render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest'
import { ProjectsPanel } from '../src/components/ProjectsPanel'
import * as queries from '../src/lib/queries'
import type { GatewayProject } from '../src/lib/gateway'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useProjects: vi.fn(),
    useProjectNext: vi.fn(),
    useProjectResume: vi.fn(),
    useRefreshProject: vi.fn(),
  }
})

const project: GatewayProject = {
  id: 1,
  name: 'kitty',
  kind: 'code',
  status: 'active',
  summary: 'a project summary',
  paths: [],
  last_touched: null,
  open_questions: [],
  next_actions: [],
  links: [],
}

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <ProjectsPanel />
    </QueryClientProvider>,
  )
}

describe('ProjectsPanel recent files (Project Resume: Artifacts, slice 1)', () => {
  beforeEach(() => {
    vi.mocked(queries.useProjects).mockReturnValue({
      data: [project], isLoading: false, isError: false, error: null,
    } as never)
    vi.mocked(queries.useProjectNext).mockReturnValue({
      data: { project_id: 1, step: 'ship the slice', why: 'it matters', recent_win: '', delegable: false, generated_at: 1 },
      isLoading: false, isError: false, error: null,
    } as never)
    vi.mocked(queries.useRefreshProject).mockReturnValue({
      mutate: vi.fn(), isPending: false, variables: undefined,
    } as never)
  })

  afterEach(cleanup)

  it('renders up to 5 recent artifacts with name, kind, state, and date', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: {
        id: 1,
        artifacts: [
          { id: 'a1', kind: 'text', display_name: 'notes.md', state: 'ready', created_at: 1750000000, media_type: 'text/plain', size_bytes: 10 },
          { id: 'a2', kind: 'image', display_name: 'diagram.png', state: 'ready', created_at: 1750000100, media_type: 'image/png', size_bytes: 20 },
        ],
      },
      isLoading: false, isError: false, error: null,
    } as never)
    renderPanel()

    expect(screen.getByText('recent files')).toBeInTheDocument()
    expect(screen.getByText('notes.md')).toBeInTheDocument()
    expect(screen.getByText('diagram.png')).toBeInTheDocument()
    expect(screen.getByText(/text.*ready/)).toBeInTheDocument()
  })

  it('renders nothing for recent files when the project has zero artifacts', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: { id: 1, artifacts: [] },
      isLoading: false, isError: false, error: null,
    } as never)
    renderPanel()

    expect(screen.queryByText('recent files')).not.toBeInTheDocument()
    // the rest of the card is unaffected by the empty artifacts list
    expect(screen.getByText('kitty')).toBeInTheDocument()
    expect(screen.getByText('ship the slice')).toBeInTheDocument()
  })

  it('does not break the rest of the card when the resume fetch errors', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: new Error('gateway exploded'),
    } as never)
    renderPanel()

    // summary and next-step still render even though artifacts failed to load
    expect(screen.getByText('a project summary')).toBeInTheDocument()
    expect(screen.getByText('ship the slice')).toBeInTheDocument()
    expect(screen.getByText(/recent files unavailable/)).toBeInTheDocument()
    expect(screen.getByText(/gateway exploded/)).toBeInTheDocument()
    expect(screen.queryByText('recent files')).not.toBeInTheDocument()
  })
})
