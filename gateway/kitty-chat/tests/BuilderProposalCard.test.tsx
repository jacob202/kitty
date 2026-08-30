import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { BuilderProposalCard } from '../src/components/builder/BuilderProposalCard'
import * as gateway from '../src/lib/gateway'

const { useSupervisor, useBuilderAction, mutate } = vi.hoisted(() => ({
  useSupervisor: vi.fn(),
  useBuilderAction: vi.fn(),
  mutate: vi.fn(),
}))

vi.mock('../src/lib/work', () => ({ useSupervisor, useBuilderAction }))
vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    proposeBuilderJob: vi.fn(),
    approveBuilderJob: vi.fn(),
    resumeBuilderJob: vi.fn(),
  }
})

const task = {
  objective: 'Fix the flaky retry loop',
  instructions: 'Cap the retry loop at max_attempts.',
  allowed_paths: ['gateway/private-secret.ts'],
  acceptance_criteria: ['Retry loop stops at max_attempts.'],
}

const preparedProposal: gateway.ConversationProposal = {
  ok: true,
  state: 'prepared',
  mission_id: 'conv-fix-the-flaky-retry-loop-1',
  manifest_sha256: 'a'.repeat(64),
  expected_base_sha: 'b'.repeat(40),
  approval_nonce: 'c'.repeat(64),
  warnings: [],
  prepared_manifest: { packets: [{ acceptance_criteria: task.acceptance_criteria }] },
  design: { path: 'docs/private-design.md', sha: 'd'.repeat(40) },
  plan: { path: 'docs/private-plan.md', sha: 'e'.repeat(40) },
}

function resumePayload(overrides: Record<string, unknown> = {}): gateway.ConversationResume {
  return {
    ok: true,
    mission: { id: 'conv-fix-the-flaky-retry-loop-1', state: 'queued' },
    current_work: { task_id: 'task-private-id', state: 'queued' },
    ...overrides,
  }
}

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

beforeEach(() => {
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear(),
    },
  })
  useSupervisor.mockReturnValue({ data: { running: false, eligible_now: 1 }, refetch: vi.fn() })
  useBuilderAction.mockReturnValue({ mutate, isPending: false })
})

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.mocked(gateway.proposeBuilderJob).mockReset()
  vi.mocked(gateway.approveBuilderJob).mockReset()
  vi.mocked(gateway.resumeBuilderJob).mockReset()
  useSupervisor.mockReset()
  useBuilderAction.mockReset()
  mutate.mockReset()
})

describe('BuilderProposalCard', () => {
  it('does not create a job merely by rendering and hides internal details', () => {
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    expect(screen.getAllByText(task.objective).length).toBeGreaterThan(0)
    expect(screen.getByText(task.instructions)).toBeInTheDocument()
    expect(screen.getByText(task.acceptance_criteria[0])).toBeInTheDocument()
    expect(screen.queryByText(task.allowed_paths[0])).not.toBeInTheDocument()
    expect(screen.queryByText(preparedProposal.mission_id)).not.toBeInTheDocument()
    expect(screen.queryByText(preparedProposal.design.path)).not.toBeInTheDocument()
    expect(screen.queryByText(preparedProposal.plan.path)).not.toBeInTheDocument()
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()
  })

  it('flags a malformed proposal without calling propose', () => {
    renderWithQueryClient(<BuilderProposalCard task={{ objective: '', instructions: '', allowed_paths: [] }} chatId="chat-1" messageIndex={0} />)
    expect(screen.getByText(/could not prepare/i)).toBeInTheDocument()
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
  })

  it('uses one plain recovery action when proposal preparation fails', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockRejectedValue(new Error('POST /builder/conversation/propose failed: 503'))
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(screen.getByRole('button', { name: /prepare this work/i }))
    expect(await screen.findByText(/could not prepare this work/i)).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(screen.queryByText(/503|propose/)).not.toBeInTheDocument()
  })

  it('prepares, then sends one nonce-bound approval without a duplicate confirm step', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({ ok: true, state: 'accepted', mission_id: preparedProposal.mission_id })
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({ mission: { id: preparedProposal.mission_id, state: 'queued' } }))

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(screen.getByRole('button', { name: /prepare this work/i }))
    await waitFor(() => expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce())
    expect(screen.getByRole('button', { name: /send this work to builder/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^confirm$/i })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /send this work to builder/i }))
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledOnce())
    expect(gateway.approveBuilderJob).toHaveBeenCalledWith(expect.objectContaining({
      prepared_manifest: preparedProposal.prepared_manifest,
      expected_manifest_sha: preparedProposal.manifest_sha256,
      expected_base_sha: preparedProposal.expected_base_sha,
      approval_nonce: preparedProposal.approval_nonce,
      confirmed: true,
    }), expect.anything())
    expect(window.localStorage.getItem('kitty.builder-proposal.chat-1.0')).toBe(preparedProposal.mission_id)
  })

  it('keeps the prepared proposal and offers one safe retry when sending fails', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob)
      .mockRejectedValueOnce(new Error('POST /builder/conversation/approve failed: 503'))
      .mockResolvedValueOnce({ ok: true, mission_id: preparedProposal.mission_id })
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload())

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(screen.getByRole('button', { name: /prepare this work/i }))
    fireEvent.click(await screen.findByRole('button', { name: /send this work to builder/i }))
    expect(await screen.findByText(/could not send this work/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try sending again/i })).toBeInTheDocument()
    expect(screen.queryByText(/503|approve/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /try sending again/i }))
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledTimes(2))
    expect(window.localStorage.getItem('kitty.builder-proposal.chat-1.0')).toBe(preparedProposal.mission_id)
  })

  it('shows every durable state in plain language and does not render identifiers', async () => {
    const states = [
      ['queued', /queued/i],
      ['running', /in progress/i],
      ['blocked', /blocked/i],
      ['failed', /failed/i],
      ['awaiting_review', /waiting for review/i],
      ['cancelled', /cancelled/i],
      ['completed', /completed/i],
    ] as const
    for (const [state, label] of states) {
      cleanup()
      window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-private-id')
      vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({
        mission: { id: 'mission-private-id', state },
        current_work: { task_id: 'task-private-id', state },
      }))
      renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
      expect((await screen.findAllByText(label)).length).toBeGreaterThan(0)
      expect(screen.queryByText('mission-private-id')).not.toBeInTheDocument()
      expect(screen.queryByText('task-private-id')).not.toBeInTheDocument()
      vi.mocked(gateway.resumeBuilderJob).mockReset()
    }
  })

  it('maps ready work to the existing supervisor tick', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-ready')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({ mission: { id: 'mission-ready', state: 'queued' }, current_work: { task_id: 'task-ready', state: 'queued' } }))
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(await screen.findByRole('button', { name: /start this work/i }))
    expect(mutate).toHaveBeenCalledWith('tick', expect.anything())
  })

  it('maps retry, resume, and cancel to the existing Builder commands', async () => {
    const cases = [
      ['failed', /try again/i, { action: 'requeue', task_id: 'task-private-id' }],
      ['paused', /resume this work/i, { action: 'resume', initiative_id: 'mission-private-id' }],
      ['running', /cancel this work/i, { action: 'cancel', task_id: 'task-private-id' }],
    ] as const
    for (const [state, label, command] of cases) {
      cleanup()
      mutate.mockReset()
      window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-private-id')
      vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({ mission: { id: 'mission-private-id', state }, current_work: { task_id: 'task-private-id', state } }))
      renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
      fireEvent.click(await screen.findByRole('button', { name: label }))
      expect(mutate).toHaveBeenCalledWith(expect.objectContaining(command), expect.anything())
      vi.mocked(gateway.resumeBuilderJob).mockReset()
    }
  })

  it('grants one more attempt when durable projection says retries are exhausted', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-private-id')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({
      mission: { id: 'mission-private-id', state: 'active' },
      current_work: { packet_id: 'PACKET-001', task_id: 'task-private-id', state: 'queued', attempt_count: 3 },
      next_action: 'exhausted',
    }))
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(await screen.findByRole('button', { name: /try again/i }))
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({
      action: 'grant_attempt',
      initiative_id: 'mission-private-id',
      packet_id: 'PACKET-001',
    }), expect.anything())
  })

  it('offers a manual status refresh and keeps the persisted mission after resume failure', async () => {
    const refetch = vi.fn()
    useSupervisor.mockReturnValue({ data: { running: true, eligible_now: 0 }, refetch })
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-still-known')
    vi.mocked(gateway.resumeBuilderJob).mockRejectedValue(new Error('GET /builder/conversation/resume failed: 500'))
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    expect(await screen.findByText(/could not refresh this work/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /prepare this work/i })).not.toBeInTheDocument()
    expect(window.localStorage.getItem('kitty.builder-proposal.chat-1.0')).toBe('mission-still-known')
    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows a safe completed result and validation/review state', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-complete')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({
      mission: { id: 'mission-complete', state: 'completed' },
      current_work: { task_id: 'task-private-id', state: 'done' },
      evidence: {
        implementation: { summary: 'Retry loop now stops at the configured limit.' },
        validation: { status: 'passed', summary: 'Focused checks passed.' },
        review: { verdict: 'approved', summary: 'Independent review approved.' },
      },
    }))
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    expect(await screen.findByText(/retry loop now stops/i)).toBeInTheDocument()
    expect(screen.getByText(/validation passed/i)).toBeInTheDocument()
    expect(screen.getByText(/review complete/i)).toBeInTheDocument()
  })

  it('uses one plain recovery action for refused commands and approval failures', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'mission-private-id')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue(resumePayload({ mission: { id: 'mission-private-id', state: 'failed' }, current_work: { task_id: 'task-private-id', state: 'failed' } }))
    mutate.mockImplementation((_command: unknown, handlers: { onSuccess: (value: unknown) => void }) => handlers.onSuccess({ ok: false, error: 'task-private-id not found' }))
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(await screen.findByRole('button', { name: /try again/i }))
    expect(await screen.findByText(/could not update this work/i)).toBeInTheDocument()
    expect(screen.queryByText(/task-private-id/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })
})
