import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { GatewayNextStep, GatewayProject } from '../src/lib/gateway'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useProjectResume: vi.fn(),
    useSetActiveProject: vi.fn(),
  }
})

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
  next_actions: ['Review Wave 3', 'Ship project workspace'],
  links: [],
}

const nextStep: GatewayNextStep = {
  project_id: 1,
  step: 'Ship the project workspace.',
  why: 'It makes project context usable.',
  recent_win: 'Activity Center is implemented.',
  delegable: false,
  generated_at: 1,
}

let setActiveProject: ReturnType<typeof vi.fn>

function renderWorkspace(onNavigate = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return {
    onNavigate,
    ...render(
      <QueryClientProvider client={client}>
        <ProjectWorkspace project={project} nextStep={nextStep} onClose={vi.fn()} onNavigate={onNavigate} />
      </QueryClientProvider>,
    ),
  }
}

beforeEach(() => {
  vi.mocked(queries.useProjectResume).mockReturnValue({
    data: {
      id: 1,
      artifacts: [{ id: 'a1', kind: 'text', display_name: 'plan.md', state: 'ready', created_at: 1788200100, media_type: 'text/markdown', size_bytes: 120 }],
      work: { items: [{ id: 'w1', title: 'Wave 4', state: 'active', next_action: 'implement workspace', updated_at: '2026-08-31T18:00:00Z' }], total_items: 1 },
      conversations: { items: [{ id: 'c1', title: 'Repo steal', objective: 'Make Kitty visibly better', updated_at: 1788200200 }], error: null },
      deadlines: { items: [{ id: 3, due_date: '2026-09-02', obligation: 'Review Wave 4', amount: null, currency: null, confidence: 'high', status: 'open' }], error: null },
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
})

afterEach(cleanup)

describe('ProjectWorkspace', () => {
  it('turns Project Resume data into a visible workspace', () => {
    renderWorkspace()

    expect(screen.getByRole('dialog', { name: /kitty project workspace/i })).toBeVisible()
    expect(screen.queryByText('project workspace', { exact: true })).not.toBeInTheDocument()
    expect(screen.getByText('Ship the project workspace.')).toBeVisible()
    expect(screen.getByText('Repo steal')).toBeVisible()
    expect(screen.getByText('Review Wave 4')).toBeVisible()
    expect(screen.getByText('Wave 4')).toBeVisible()
    expect(screen.getByText('plan.md')).toBeVisible()
  })

  it('moves keyboard focus into the project workspace when it opens', () => {
    renderWorkspace()
    expect(screen.getByRole('button', { name: 'Close project workspace' })).toHaveFocus()
  })

  it('activates the project before continuing in chat', async () => {
    const onNavigate = vi.fn()
    renderWorkspace(onNavigate)

    fireEvent.click(screen.getByRole('button', { name: /continue in chat/i }))

    await waitFor(() => expect(setActiveProject).toHaveBeenCalledWith(1))
    expect(onNavigate).toHaveBeenCalledWith('chat')
  })
})
