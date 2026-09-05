import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { BuilderProposalCard } from '../src/components/builder/BuilderProposalCard'
import * as gateway from '../src/lib/gateway'

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
  allowed_paths: ['gateway/'],
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
  prepared_manifest: {
    packets: [{ acceptance_criteria: ['Retry loop stops at max_attempts.'] }],
  },
  design: { path: 'docs/superpowers/specs/x-design.md', sha: 'd'.repeat(40) },
  plan: { path: 'docs/superpowers/plans/x.md', sha: 'e'.repeat(40) },
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
})

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.mocked(gateway.proposeBuilderJob).mockReset()
  vi.mocked(gateway.approveBuilderJob).mockReset()
  vi.mocked(gateway.resumeBuilderJob).mockReset()
})

describe('BuilderProposalCard', () => {
  it('does not create a job merely by rendering the proposal', () => {
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    expect(screen.getAllByText(/Fix the flaky retry loop/).length).toBeGreaterThan(0)
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()
  })

  it('flags a malformed proposal without calling propose', () => {
    renderWithQueryClient(
      <BuilderProposalCard
        task={{ objective: '', instructions: '', allowed_paths: [] }}
        chatId="chat-1"
        messageIndex={0}
      />,
    )

    expect(screen.getByText(/Malformed Builder proposal/)).toBeInTheDocument()
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
  })

  it('edits the proposal before compiling the Mission', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    fireEvent.click(screen.getByRole('button', { name: 'Edit proposal' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Proposal objective' }), { target: { value: 'Fix only the retry cap' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Proposal instructions' }), { target: { value: 'Change only the retry cap and preserve all other behavior.' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Proposal allowed paths' }), { target: { value: 'gateway/retry.py\ntests/test_retry.py' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save proposal changes' }))

    expect(screen.getAllByText(/Fix only the retry cap/).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    await waitFor(() => expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce())
    expect(gateway.proposeBuilderJob).toHaveBeenCalledWith(
      expect.objectContaining({
        objective: 'Fix only the retry cap',
        instructions: 'Change only the retry cap and preserve all other behavior.',
        allowed_paths: ['gateway/retry.py', 'tests/test_retry.py'],
      }),
      expect.anything(),
    )
  })

  it('compiles the task, then requires a confirm step before approving', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({
      ok: true,
      state: 'accepted',
      mission_id: preparedProposal.mission_id,
    })
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: preparedProposal.mission_id, state: 'accepted' },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    await waitFor(() => expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce())
    expect(gateway.proposeBuilderJob).toHaveBeenCalledWith(
      expect.objectContaining({ objective: task.objective, allowed_paths: task.allowed_paths }),
      expect.anything(),
    )

    const approveButton = await screen.findByText('Approve')
    fireEvent.click(approveButton)
    expect(screen.getByText(/execution route under current policy/i)).toBeInTheDocument()
    expect(screen.queryByText(/free worker/i)).not.toBeInTheDocument()

    // Clicking Approve must not itself create the job — it only opens the
    // confirm step; the mutation fires on the explicit Confirm click.
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()

    fireEvent.click(screen.getByText('Confirm'))

    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledOnce())
    expect(gateway.approveBuilderJob).toHaveBeenCalledWith(
      expect.objectContaining({
        prepared_manifest: preparedProposal.prepared_manifest,
        expected_manifest_sha: preparedProposal.manifest_sha256,
        expected_base_sha: preparedProposal.expected_base_sha,
        approval_nonce: preparedProposal.approval_nonce,
        confirmed: true,
      }),
      expect.anything(),
    )

    // Once approved, the card switches straight to the durable job view — the
    // mission id is persisted so a reload finds it too (see below).
    await screen.findByText(/Track it in the Work view/)
    expect(window.localStorage.getItem('kitty.builder-proposal.chat-1.0')).toBe(
      preparedProposal.mission_id,
    )
  })

  it('surfaces a refused approval instead of a false success', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({
      ok: false,
      state: 'needs_decision',
      error: 'Builder base moved; prepare a new Mission version.',
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))

    await screen.findByText(/Builder base moved/)
    expect(screen.queryByText(/Track it in the Work view/)).not.toBeInTheDocument()
    // A refused approval created nothing durable — no id to resume later.
    expect(window.localStorage.getItem('kitty.builder-proposal.chat-1.0')).toBeNull()
  })

  it('translates an unreachable gateway into a plain-language message, not the raw browser error', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockRejectedValue(new TypeError('Failed to fetch'))

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))

    await screen.findByText(/Could not reach the Kitty gateway/)
    expect(screen.queryByText('Failed to fetch')).not.toBeInTheDocument()
  })

  it('resumes a previously approved job instead of resetting to a blank Compile button', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-already-approved-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-already-approved-1', state: 'in_progress' },
      current_work: { state: 'running' },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    await screen.findByText(/conv-already-approved-1/)
    expect(screen.getByText(/running/)).toBeInTheDocument()
    expect(screen.queryByText('Compile as Builder Mission')).not.toBeInTheDocument()
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
    expect(gateway.resumeBuilderJob).toHaveBeenCalledWith('conv-already-approved-1')
  })

  it('surfaces a resume lookup failure without silently reverting to Compile', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-gone-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: false,
      error: 'mission not found',
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    await screen.findByText(/mission not found/)
    expect(screen.queryByText('Compile as Builder Mission')).not.toBeInTheDocument()
  })

  it('still shows the durable job status when resume ok:false is an unrelated health check, not a missing job', async () => {
    // resume_context()'s `ok` reflects Kitty's own cold-start health check,
    // not whether the job was found. Builder facts (mission/current_work)
    // are populated whenever the mission is found, even when `ok` is false —
    // a cold-start hiccup must never hide real job status.
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-still-there-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: false,
      error: 'Kitty cold-start receipt is not trusted; continuity needs attention.',
      mission: { id: 'conv-still-there-1', state: 'active' },
      current_work: { state: 'running' },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    await screen.findByText(/conv-still-there-1/)
    expect(screen.getByText(/running/)).toBeInTheDocument()
    expect(screen.getByText(/continuity needs attention/)).toBeInTheDocument()
    expect(screen.queryByText('Could not find this job in Builder.')).not.toBeInTheDocument()
  })

  it('keys resumed state per chat message, not globally', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-for-message-zero')

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={1} />)

    // A different messageIndex must not pick up another message's stored id.
    expect(await screen.findByText('Compile as Builder Mission')).toBeInTheDocument()
    expect(gateway.resumeBuilderJob).not.toHaveBeenCalled()
  })

  it('offers an Open in Work handoff once the job is durable', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-handoff-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-handoff-1', state: 'in_progress' },
      current_work: { state: 'running' },
    })
    const onOpenWork = vi.fn()

    renderWithQueryClient(
      <BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} onOpenWork={onOpenWork} />,
    )

    const button = await screen.findByTestId('builder-proposal-open-work')
    fireEvent.click(button)
    expect(onOpenWork).toHaveBeenCalledOnce()
  })

  it('omits the Open in Work button when the host has no Work navigation', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-no-nav-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-no-nav-1', state: 'in_progress' },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    // The durable status still renders; only the handoff action is absent.
    expect(await screen.findByText(/conv-no-nav-1/)).toBeInTheDocument()
    expect(screen.queryByTestId('builder-proposal-open-work')).not.toBeInTheDocument()
  })
})
