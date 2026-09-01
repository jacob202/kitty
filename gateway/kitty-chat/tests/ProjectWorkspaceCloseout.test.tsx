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

function renderWorkspace(props: { onNavigate?: (view: string) => void; onStartChat?: () => void } = {}) {
  return render(
    <QueryClientProvider client={client()}>
      <ProjectWorkspace
        project={project}
        nextStep={nextStep}
        onClose={vi.fn()}
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
})
