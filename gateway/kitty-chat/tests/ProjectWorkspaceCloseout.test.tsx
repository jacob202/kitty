import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { GatewayNextStep, GatewayProject } from '../src/lib/gateway'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useProjects: vi.fn(),
    useProjectNext: vi.fn(),
    useProjectNextSteps: vi.fn(),
    useProjectResume: vi.fn(),
    useRefreshProject: vi.fn(),
    useSetActiveProject: vi.fn(),
  }
})

import { ProjectsPanel } from '../src/components/ProjectsPanel'
import { ProjectWorkspace } from '../src/components/projects/ProjectWorkspace'

const project: GatewayProject = {
  id: 1,
  name: 'kitty',
  kind: 'code',
  status: 'active',
  summary: 'Build Kitty into a reliable personal workspace.',
  paths: [],
  last_touched: 1788200000,
  open_questions: [],
  next_actions: ['Ship project workspace'],
  links: [],
}

const nextStep: GatewayNextStep = {
  project_id: 1,
  step: 'Ship the project workspace.',
  why: 'It makes project context usable.',
  recent_win: '',
  delegable: false,
  generated_at: 1,
}

let setActiveProject: ReturnType<typeof vi.fn>

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
}

function renderWorkspace(props: {
  onNavigate?: (view: string) => void
  onStartChat?: () => void
  onClose?: () => void
} = {}) {
  return render(
    <QueryClientProvider client={client()}>
      <ProjectWorkspace
        project={project}
        nextStep={nextStep}
        onClose={props.onClose ?? vi.fn()}
        onNavigate={props.onNavigate ?? vi.fn()}
        onStartChat={props.onStartChat}
      />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(queries.useProjectResume).mockReturnValue({
    data: {
      id: 1,
      artifacts: [{
        id: 'a1', kind: 'image', display_name: 'plan.png', state: 'ready',
        created_at: 1788200100, media_type: 'image/png', size_bytes: 120,
      }],
      work: { items: [], total_items: 0 },
      conversations: { items: [], error: null },
      deadlines: { items: [], error: null },
    },
    isLoading: false,
    isError: false,
    error: null,
  } as never)
  setActiveProject = vi.fn(async () => ({ active_project: project }))
  vi.mocked(queries.useSetActiveProject).mockReturnValue({
    mutateAsync: setActiveProject,
    isPending: false,
    isError: false,
    error: null,
  } as never)
  vi.mocked(queries.useProjects).mockReturnValue({
    data: [project], isLoading: false, isError: false, error: null,
  } as never)
  vi.mocked(queries.useProjectNext).mockImplementation(() => {
    throw new Error('ProjectsPanel must use the bulk next-step projection')
  })
  vi.mocked(queries.useProjectNextSteps).mockReturnValue([{
    data: nextStep, isPending: false, isError: false,
  }] as never)
  vi.mocked(queries.useRefreshProject).mockReturnValue({
    mutate: vi.fn(), isPending: false, variables: undefined,
    isError: false, error: null, data: undefined,
  } as never)
})

afterEach(cleanup)

describe('Project workspace review closeout', () => {
  it('starts a fresh chat after project activation and before chat navigation', async () => {
    const order: string[] = []
    setActiveProject.mockImplementation(async () => {
      order.push('activate')
      return { active_project: project }
    })
    const onStartChat = vi.fn(() => order.push('new-chat'))
    const onNavigate = vi.fn((view: string) => order.push(`navigate:${view}`))
    renderWorkspace({ onStartChat, onNavigate })

    fireEvent.click(screen.getByRole('button', { name: /continue in chat/i }))

    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('chat'))
    expect(order).toEqual(['activate', 'new-chat', 'navigate:chat'])
  })

  it('does not let the workspace close while project activation is pending', () => {
    const onClose = vi.fn()
    vi.mocked(queries.useSetActiveProject).mockReturnValue({
      mutateAsync: vi.fn(() => new Promise(() => {})),
      isPending: true,
      isError: false,
      error: null,
    } as never)
    renderWorkspace({ onClose })

    const close = screen.getByRole('button', { name: /close project workspace/i })
    expect(close).toBeDisabled()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('stays below the global command palette and hides the parent dialog during artifact preview', () => {
    renderWorkspace()
    const dialog = screen.getByRole('dialog', { name: /kitty project workspace/i })
    const backdrop = dialog.parentElement as HTMLElement

    expect(Number(backdrop.style.zIndex)).toBeLessThan(1000)
    fireEvent.click(screen.getByRole('button', { name: /open plan.png/i }))

    expect(dialog).toHaveAttribute('aria-hidden', 'true')
    expect(dialog).toHaveAttribute('inert')
    expect(screen.getByRole('dialog', { name: 'plan.png' })).toBeVisible()
  })

  it('surfaces a bulk next-step query failure instead of calling it an empty state', () => {
    vi.mocked(queries.useProjectNextSteps).mockReturnValue([{
      data: null, isPending: false, isError: true,
    }] as never)
    render(
      <QueryClientProvider client={client()}>
        <ProjectsPanel />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: /open workspace/i }))

    expect(screen.getByText(/couldn't read the next step/i)).toBeVisible()
    expect(screen.queryByText(/no generated next step yet/i)).not.toBeInTheDocument()
  })

  it('surfaces degraded refresh sources with their returned context', () => {
    vi.mocked(queries.useRefreshProject).mockReturnValue({
      mutate: vi.fn(), isPending: false, variables: 1,
      isError: false, error: null,
      data: {
        sources: {
          memory: { ok: false, error: 'timed out after 10s' },
          signals: { ok: false, error: 'signal store unavailable' },
        },
        next_step: { ok: true },
      },
    } as never)
    render(
      <QueryClientProvider client={client()}>
        <ProjectsPanel />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: /open workspace/i }))

    const alerts = screen.getAllByRole('alert').map(alert => alert.textContent ?? '').join(' ')
    expect(alerts).toMatch(/memory.*timed out after 10s/i)
    expect(alerts).toMatch(/signals.*signal store unavailable/i)
  })

  it('surfaces the returned partial next-step refresh error detail', () => {
    vi.mocked(queries.useRefreshProject).mockReturnValue({
      mutate: vi.fn(), isPending: false, variables: 1,
      isError: false, error: null,
      data: { next_step: { ok: false, error: 'model unavailable' } },
    } as never)
    render(
      <QueryClientProvider client={client()}>
        <ProjectsPanel />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: /open workspace/i }))

    expect(screen.getByRole('alert')).toHaveTextContent(/project refreshed, but kitty couldn't update the next step/i)
    expect(screen.getByRole('alert')).toHaveTextContent(/model unavailable/i)
  })

  it('shows degraded Builder work truth even when no work rows remain', () => {
    vi.mocked(queries.useProjectResume).mockReturnValue({
      data: {
        id: 1,
        artifacts: [],
        work: {
          items: [],
          total_items: 0,
          source: {
            kind: 'builder',
            state: 'degraded',
            reason: 'Builder snapshot integrity is partial: 1 of 2 packets are incomplete.',
          },
        },
        conversations: { items: [], error: null },
        deadlines: { items: [], error: null },
      },
      isLoading: false,
      isError: false,
      error: null,
    } as never)
    renderWorkspace()

    expect(screen.getByRole('status')).toHaveTextContent(/builder work unavailable/i)
    expect(screen.getByRole('status')).toHaveTextContent(/1 of 2 packets are incomplete/i)
  })
})
