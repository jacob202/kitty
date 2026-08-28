import { render, screen, cleanup, fireEvent } from '@testing-library/react'
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
    useProjectNextSteps: vi.fn(),
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
    vi.mocked(queries.useProjectNext).mockImplementation(() => {
      throw new Error('ProjectsPanel must use the bulk next-step projection')
    })
    vi.mocked(queries.useProjectNextSteps).mockReturnValue([{
      data: { project_id: 1, step: 'ship the slice', why: 'it matters', recent_win: '', delegable: false, generated_at: 1 },
      isPending: false, isError: false,
    }] as never)
    vi.mocked(queries.useRefreshProject).mockReturnValue({
      mutate: vi.fn(), isPending: false, variables: undefined,
    } as never)
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: { id: 1, artifacts: [], work: { items: [], total_items: 0 } },
      isLoading: false, isError: false, error: null,
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

    expect(screen.queryByText('recent files')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /project context/i }))
    expect(screen.getByText('recent files')).toBeInTheDocument()
    expect(screen.getByText('notes.md')).toBeInTheDocument()
    expect(screen.getByText('diagram.png')).toBeInTheDocument()
    expect(screen.getByText(/text.*ready/)).toBeInTheDocument()
  })

  it('renders nothing for recent files when the project has zero artifacts', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: { id: 1, artifacts: [], work: { items: [], total_items: 0 } },
      isLoading: false, isError: false, error: null,
    } as never)
    renderPanel()

    expect(screen.queryByText('recent files')).not.toBeInTheDocument()
    // the rest of the card is unaffected by the empty artifacts list
    expect(screen.getByText('kitty')).toBeInTheDocument()
    expect(screen.getByText('ship the slice')).toBeInTheDocument()
  })

  it('renders project-scoped builder work when present', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: {
        id: 1,
        artifacts: [],
        work: {
          items: [{
            id: 'init-1', title: 'Ship project linkage', state: 'active',
            next_action: 'merge the PR', updated_at: '2026-08-23T12:00:00Z',
          }],
          total_items: 1,
        },
      },
      isLoading: false, isError: false, error: null,
    } as never)
    renderPanel()

    expect(screen.queryByText('builder work')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /project context/i }))
    expect(screen.getByText('builder work')).toBeInTheDocument()
    expect(screen.getByText('Ship project linkage')).toBeInTheDocument()
    expect(screen.getByText(/active.*merge the PR/)).toBeInTheDocument()
  })

  it('does not break the rest of the card when the resume fetch errors', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: new Error('gateway exploded'),
    } as never)
    renderPanel()

    // summary and next-step still render even though related context failed to load
    expect(screen.getByText('a project summary')).toBeInTheDocument()
    expect(screen.getByText('ship the slice')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /project context/i }))
    expect(screen.getByText(/project context unavailable/)).toBeInTheDocument()
    expect(screen.getByText(/gateway exploded/)).toBeInTheDocument()
    expect(screen.queryByText('recent files')).not.toBeInTheDocument()
  })
})


describe('ProjectsPanel visual hierarchy', () => {
  beforeEach(() => {
    vi.mocked(queries.useProjects).mockReturnValue({
      data: [project], isLoading: false, isError: false, error: null,
    } as never)
    vi.mocked(queries.useProjectNext).mockImplementation(() => {
      throw new Error('ProjectsPanel must use the bulk next-step projection')
    })
    vi.mocked(queries.useProjectNextSteps).mockReturnValue([{
      data: { project_id: 1, step: 'ship the slice', why: 'it matters', recent_win: '', delegable: false, generated_at: 1 },
      isPending: false, isError: false,
    }] as never)
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: { id: 1, artifacts: [], work: { items: [], total_items: 0 } },
      isLoading: false, isError: false, error: null,
    } as never)
    vi.mocked(queries.useRefreshProject).mockReturnValue({
      mutate: vi.fn(), isPending: false, variables: undefined,
    } as never)
  })

  afterEach(cleanup)

  it('leaves the page heading to ProjectsView instead of rendering a duplicate', () => {
    renderPanel()
    expect(screen.queryByRole('heading', { name: /^projects$/i })).not.toBeInTheDocument()
  })

  it('renders projects inside one shared list surface', () => {
    renderPanel()
    expect(screen.getByTestId('project-list')).toBeInTheDocument()
    expect(screen.getAllByTestId('project-row')).toHaveLength(1)
  })

  it('keeps project context closed until the user asks for it', () => {
    renderPanel()
    const context = screen.getByRole('button', { name: /project context/i })
    expect(context).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('builder work')).not.toBeInTheDocument()
    expect(screen.queryByText('recent files')).not.toBeInTheDocument()
  })

  it('uses a neutral semantic surface for the next step', () => {
    renderPanel()
    const next = screen.getByTestId('project-next-step')
    const style = next.getAttribute('style') ?? ''
    expect(style).toContain('background: var(--color-surface-elevated)')
    expect(style).toContain('border: 1px solid var(--color-separator)')
    expect(style).not.toContain('var(--color-accent)')
  })

  it('keeps refresh touch-sized', () => {
    renderPanel()
    expect(screen.getByRole('button', { name: /refresh/i })).toHaveStyle({ minHeight: '44px' })
  })
})


describe('ProjectsPanel context empty state', () => {
  beforeEach(() => {
    vi.mocked(queries.useProjects).mockReturnValue({ data: [project], isLoading: false, isError: false, error: null } as never)
    vi.mocked(queries.useProjectNext).mockImplementation(() => { throw new Error('per-project next-step hook should stay unused') })
    vi.mocked(queries.useProjectNextSteps).mockReturnValue([{ data: null, isPending: false, isError: false }] as never)
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: { id: 1, artifacts: [], work: { items: [], total_items: 0 } },
      isLoading: false, isError: false, error: null,
    } as never)
    vi.mocked(queries.useRefreshProject).mockReturnValue({ mutate: vi.fn(), isPending: false, variables: undefined } as never)
  })

  afterEach(cleanup)

  it('shows a truthful empty state when disclosed context has nothing else', () => {
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /project context/i }))
    expect(screen.getByText(/no related work or recent files yet/i)).toBeInTheDocument()
  })
})
