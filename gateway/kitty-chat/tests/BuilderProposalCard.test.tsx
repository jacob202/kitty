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
    fetchMission: vi.fn(),
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
  gateway_mission_id: 'gateway-conversation:conv-fix-the-flaky-retry-loop-1',
  gateway_mission_status: 'PLAN_REVIEW',
  gateway_plan_digest: 'a'.repeat(64),
  gateway_plan_review_state: 'approved',
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
  vi.mocked(gateway.fetchMission).mockResolvedValue({
    mission_id: preparedProposal.gateway_mission_id as string,
    objective: task.objective,
    definition_of_done: task.acceptance_criteria,
    status: 'PLAN_REVIEW',
    supervisor: { id: 'kitty', epoch: 1 },
    plan: { review_state: 'approved', digest: preparedProposal.gateway_plan_digest },
  })
})

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.mocked(gateway.proposeBuilderJob).mockReset()
  vi.mocked(gateway.approveBuilderJob).mockReset()
  vi.mocked(gateway.resumeBuilderJob).mockReset()
  vi.mocked(gateway.fetchMission).mockReset()
})

describe('BuilderProposalCard', () => {
  it('does not create a job merely by rendering the proposal', () => {
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    expect(screen.getAllByText(/Fix the flaky retry loop/).length).toBeGreaterThan(0)
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()
  })

  it('shows the proposal route before the user approves anything', () => {
    const routedTask = {
      ...task,
      route: { provider: 'openrouter', model: 'deepseek-v4-flash', estimated_cost_cad: 0.0123 },
    }

    renderWithQueryClient(<BuilderProposalCard task={routedTask} chatId="chat-route" messageIndex={0} />)

    const route = screen.getByText(/Proposal route:/).closest('p')
    expect(route).not.toBeNull()
    expect(route).toHaveTextContent('openrouter · deepseek-v4-flash · est. CAD 0.0123')
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()
  })

  it('never relabels proposal routing as the Builder execution route', async () => {
    const routedTask = {
      ...task,
      route: { provider: 'openrouter', model: 'deepseek-v4-flash', estimated_cost_cad: 0.0123 },
    }
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)

    renderWithQueryClient(<BuilderProposalCard task={routedTask} chatId="chat-route-prepared" messageIndex={0} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))

    expect(await screen.findByText('Approve')).toBeInTheDocument()
    expect(screen.queryByText(/Execution route:/)).not.toBeInTheDocument()
    expect(screen.getAllByText(/Proposal route:/).length).toBeGreaterThan(0)
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


  it('reuses the same explicit initiative after a dropped proposal response and remount', async () => {
    vi.mocked(gateway.proposeBuilderJob)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockImplementationOnce(async (payload) => ({
        ...preparedProposal,
        mission_id: payload.initiative_id,
      }))

    const first = renderWithQueryClient(
      <BuilderProposalCard task={task} chatId="chat-proposal-loss" messageIndex={4} />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    await screen.findByText(/Could not reach the Kitty gateway/)

    const firstPayload = vi.mocked(gateway.proposeBuilderJob).mock.calls[0]?.[0]
    expect(firstPayload?.initiative_id).toMatch(/^conv-ui-[a-z0-9]+$/)
    const checkpoint = JSON.parse(
      window.localStorage.getItem('kitty.builder-proposal.chat-proposal-loss.4') as string,
    )
    expect(checkpoint).toMatchObject({
      version: 2,
      state: 'proposal',
      initiativeId: firstPayload?.initiative_id,
      task,
    })

    first.unmount()
    renderWithQueryClient(
      <BuilderProposalCard task={task} chatId="chat-proposal-loss" messageIndex={4} />,
    )
    fireEvent.click(await screen.findByText('Compile as Builder Mission'))

    await waitFor(() => expect(gateway.proposeBuilderJob).toHaveBeenCalledTimes(2))
    const secondPayload = vi.mocked(gateway.proposeBuilderJob).mock.calls[1]?.[0]
    expect(secondPayload?.initiative_id).toBe(firstPayload?.initiative_id)
  })

  it('does not expose Builder execution approval while independent plan review is pending', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue({
      ...preparedProposal,
      gateway_plan_review_state: 'unreviewed',
    })
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-review" messageIndex={0} />)

    fireEvent.click(screen.getByText('Compile as Builder Mission'))

    expect(await screen.findByText(/Independent plan review pending/i)).toBeInTheDocument()
    expect(screen.queryByText('Approve')).not.toBeInTheDocument()
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()
  })



  it('reloads a prepared Gateway Mission without recompiling while plan review is pending', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue({
      ...preparedProposal,
      gateway_plan_review_state: 'unreviewed',
    })
    vi.mocked(gateway.fetchMission).mockResolvedValue({
      mission_id: preparedProposal.gateway_mission_id as string,
      objective: task.objective,
      definition_of_done: task.acceptance_criteria,
      status: 'PLAN_REVIEW',
      supervisor: { id: 'kitty', epoch: 1 },
      plan: { review_state: 'unreviewed', digest: preparedProposal.gateway_plan_digest },
    })

    const first = renderWithQueryClient(
      <BuilderProposalCard task={task} chatId="chat-prepared-reload" messageIndex={2} />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    expect(await screen.findByText(/Independent plan review pending/i)).toBeInTheDocument()
    await waitFor(() => expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce())

    const checkpoint = JSON.parse(
      window.localStorage.getItem('kitty.builder-proposal.chat-prepared-reload.2') as string,
    )
    expect(checkpoint).toMatchObject({
      version: 3,
      state: 'prepared',
      initiativeId: preparedProposal.mission_id,
      gatewayMissionId: preparedProposal.gateway_mission_id,
      task,
    })

    first.unmount()
    renderWithQueryClient(
      <BuilderProposalCard task={task} chatId="chat-prepared-reload" messageIndex={2} />,
    )

    expect(await screen.findByText(/Independent plan review pending/i)).toBeInTheDocument()
    expect(screen.queryByText('Compile as Builder Mission')).not.toBeInTheDocument()
    expect(gateway.fetchMission).toHaveBeenCalledWith(preparedProposal.gateway_mission_id)
    expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce()
  })

  it('automatically unlocks approval when durable Mission review becomes approved', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue({
      ...preparedProposal,
      gateway_plan_review_state: 'unreviewed',
    })
    vi.mocked(gateway.fetchMission).mockResolvedValue({
      mission_id: preparedProposal.gateway_mission_id as string,
      objective: task.objective,
      definition_of_done: task.acceptance_criteria,
      status: 'PLAN_REVIEW',
      supervisor: { id: 'kitty', epoch: 1 },
      plan: { review_state: 'approved', digest: preparedProposal.gateway_plan_digest },
    })
    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-auto-review" messageIndex={0} />)

    fireEvent.click(screen.getByText('Compile as Builder Mission'))

    expect(await screen.findByText('Approve')).toBeInTheDocument()
    expect(gateway.fetchMission).toHaveBeenCalledWith(preparedProposal.gateway_mission_id)
    expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce()
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

  it('recovers when approval commits ambiguously instead of compiling a duplicate job', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({
        ok: true,
        state: 'accepted',
        mission_id: preparedProposal.mission_id,
        apply_status: 'unchanged',
      })
    vi.mocked(gateway.resumeBuilderJob)
      .mockResolvedValueOnce({
        ok: false,
        state: 'unknown',
        error_code: 'work_not_found',
        error: `Builder work not found: ${preparedProposal.mission_id}`,
      })
      .mockResolvedValue({
        ok: true,
        mission: { id: preparedProposal.mission_id, state: 'active' },
        current_work: { state: 'queued' },
      })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))

    const retry = await screen.findByRole('button', { name: 'Retry same approval' })
    const checkpoint = JSON.parse(
      window.localStorage.getItem('kitty.builder-proposal.chat-1.0') as string,
    )
    expect(checkpoint).toMatchObject({
      version: 1,
      state: 'pending',
      missionId: preparedProposal.mission_id,
      approval: {
        expected_manifest_sha: preparedProposal.manifest_sha256,
        expected_base_sha: preparedProposal.expected_base_sha,
        approval_nonce: preparedProposal.approval_nonce,
        confirmed: true,
      },
    })
    expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce()

    fireEvent.click(retry)

    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledTimes(2))
    await screen.findByText(/Track it in the Work view/)
    expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce()
    expect(window.localStorage.getItem('kitty.builder-proposal.chat-1.0')).toBe(
      preparedProposal.mission_id,
    )
  })


  it('preserves the immutable approval checkpoint when Builder accepted but Mission binding needs recovery', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({
      ok: false,
      state: 'recovery_required',
      error_code: 'mission_binding_failed',
      error: 'Builder accepted the work but Mission binding needs reconciliation.',
      gateway_mission_id: preparedProposal.gateway_mission_id,
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-binding" messageIndex={0} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))

    await screen.findByText(/Mission binding needs reconciliation/)
    const checkpoint = JSON.parse(
      window.localStorage.getItem('kitty.builder-proposal.chat-binding.0') as string,
    )
    expect(checkpoint).toMatchObject({
      version: 1,
      state: 'pending',
      missionId: preparedProposal.mission_id,
      approval: { gateway_mission_id: preparedProposal.gateway_mission_id, confirmed: true },
    })
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

  it('does not call an in-flight Builder job paused when no other packet is eligible', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-running-in-flight')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-running-in-flight', state: 'paused' },
      current_work: { state: 'running' },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    const missionLabel = await screen.findByText(/Mission:/)
    const missionLine = missionLabel.closest('p')
    expect(missionLine).not.toBeNull()
    expect(missionLine).toHaveTextContent(/in progress/)
    expect(missionLine).not.toHaveTextContent(/paused/)
    const currentWorkLine = screen.getByText(/Current work:/).closest('p')
    expect(currentWorkLine).not.toBeNull()
    expect(currentWorkLine).toHaveTextContent(/running/)
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

  it('renders unaccepted work as attention and exposes the Mission-store failure cause', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-awaiting-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-awaiting-1', state: 'complete' },
      current_work: { state: 'completed' },
      builder_task_complete: true,
      awaiting_acceptance: true,
      mission_acceptance: {
        state: 'unavailable',
        accepted: null,
        error: 'Mission store is locked',
      },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    const attention = await screen.findByTestId('builder-job-awaiting-acceptance')
    expect(attention).toHaveTextContent(/Built, not accepted yet/)
    expect(attention).toHaveTextContent(/Acceptance records are temporarily locked/)
    expect(attention).toHaveTextContent(/Check Kitty status, then retry/)
    expect(attention).toHaveStyle({ border: '1px solid #FF9800' })
    expect(attention).not.toHaveStyle({ border: '1px solid #4CAF50' })
  })

  it('shows a Mission-store outage as attention while Builder is still running', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-running-degraded-1')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-running-degraded-1', state: 'active' },
      current_work: { state: 'running' },
      builder_task_complete: false,
      awaiting_acceptance: false,
      mission_acceptance: {
        state: 'unavailable',
        accepted: null,
        error: 'Mission store is locked',
      },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    const attention = await screen.findByTestId('builder-job-acceptance-unavailable')
    expect(attention).toHaveTextContent(/Acceptance status unavailable/)
    expect(attention).toHaveTextContent(/Acceptance records are temporarily locked/)
    expect(attention).toHaveStyle({ border: '1px solid #FF9800' })
    expect(attention).not.toHaveStyle({ border: '1px solid #4CAF50' })
    expect(screen.queryByText(/Built, not accepted yet/)).not.toBeInTheDocument()
  })

  it('never exposes raw Mission or SQLite diagnostics in the running acceptance warning', async () => {
    window.localStorage.setItem('kitty.builder-proposal.chat-1.0', 'conv-running-raw-outage')
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: 'conv-running-raw-outage', state: 'paused' },
      current_work: { state: 'running' },
      builder_task_complete: false,
      awaiting_acceptance: false,
      mission_acceptance: {
        state: 'unavailable',
        accepted: null,
        error: 'MissionError: Mission store is unavailable: no such table: missions',
      },
    })

    renderWithQueryClient(<BuilderProposalCard task={task} chatId="chat-1" messageIndex={0} />)

    const attention = await screen.findByTestId('builder-job-acceptance-unavailable')
    expect(attention).toHaveTextContent(/Acceptance records are temporarily unavailable/)
    expect(attention).not.toHaveTextContent(/MissionError/)
    expect(attention).not.toHaveTextContent(/no such table/)
    expect(attention).not.toHaveTextContent(/missions/)
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

  it('does not let an old numbered Work key hijack a new pending-only Work proposal', async () => {
    window.localStorage.setItem('kitty.builder-proposal.work-builder-request.1', 'conv-old-work-job')

    renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={1}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )

    expect(await screen.findByText('Compile as Builder Mission')).toBeInTheDocument()
    expect(gateway.resumeBuilderJob).not.toHaveBeenCalled()
  })

  it('clears the pending-only Work checkpoint once approval is durably accepted', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({ ok: true, state: 'accepted', mission_id: preparedProposal.mission_id })
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({ ok: true, mission: { id: preparedProposal.mission_id, state: 'accepted' } })

    renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={1}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))

    await screen.findByText(/Track it in the Work view/)
    expect(window.localStorage.getItem('kitty.builder-proposal.work.pending')).toBeNull()
    expect(window.localStorage.getItem('kitty.builder-proposal.work-builder-request.1')).toBeNull()
  })

  it('reloads the exact pending-only Work approval and clears it when the durable mission is found', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: preparedProposal.mission_id, state: 'active' },
      current_work: { state: 'queued' },
      // The receipt proves the binding resolved only by reporting a real
      // acceptance state; an unavailable one would mean it is still unproven.
      mission_acceptance: { state: 'unreviewed', mission_id: 'mission_gateway_1' },
    })

    const first = renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={1}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledOnce())
    expect(JSON.parse(window.localStorage.getItem('kitty.builder-proposal.work.pending') as string)).toMatchObject({
      state: 'pending',
      missionId: preparedProposal.mission_id,
      task,
    })

    first.unmount()
    vi.mocked(gateway.resumeBuilderJob).mockClear()
    renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={99}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )

    expect(await screen.findByText(/Track it in the Work view/)).toBeInTheDocument()
    expect(gateway.resumeBuilderJob).toHaveBeenCalledWith(preparedProposal.mission_id)
    await waitFor(() => expect(window.localStorage.getItem('kitty.builder-proposal.work.pending')).toBeNull())
    expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce()
    expect(gateway.approveBuilderJob).toHaveBeenCalledOnce()
  })

  it('keeps the pending approval retry while the Mission binding is still missing after reload', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: preparedProposal.mission_id, state: 'active' },
      current_work: { state: 'queued' },
      awaiting_acceptance: true,
      awaiting_acceptance_because: 'Expected Gateway Mission binding is missing',
      mission_acceptance: {
        state: 'unavailable',
        error: `Expected Gateway Mission binding is missing for Builder initiative ${preparedProposal.mission_id}`,
      },
    })

    const first = renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={1}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledOnce())

    // Reload: Builder's durable job is found, but its Gateway Mission binding
    // is not. The exact approval payload is the only way to reconcile that.
    first.unmount()
    vi.mocked(gateway.resumeBuilderJob).mockClear()
    renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={2}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )

    expect(await screen.findByRole('button', { name: 'Retry same approval' })).toBeInTheDocument()
    await screen.findByText(/Mission binding is still missing/)
    const checkpoint = JSON.parse(
      window.localStorage.getItem('kitty.builder-proposal.work.pending') as string,
    )
    expect(checkpoint).toMatchObject({
      version: 1,
      state: 'pending',
      missionId: preparedProposal.mission_id,
      approval: {
        expected_manifest_sha: preparedProposal.manifest_sha256,
        approval_nonce: preparedProposal.approval_nonce,
        confirmed: true,
      },
    })
    expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce()
  })

  it('keeps the checkpoint when the Mission store is unavailable for another reason', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: preparedProposal.mission_id, state: 'active' },
      current_work: { state: 'queued' },
      awaiting_acceptance: true,
      awaiting_acceptance_because: 'the Mission store could not be read',
      mission_acceptance: {
        state: 'unavailable',
        error: 'MissionError: Mission store is unavailable: database changed while snapshotting',
      },
    })

    const first = renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={1}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledOnce())
    first.unmount()

    renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={2}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )

    // The store outage is not proof the binding resolved. The exact checkpoint
    // is the only way to reconcile the approval once the store recovers.
    expect(await screen.findByRole('button', { name: 'Retry same approval' })).toBeInTheDocument()
    const checkpoint = JSON.parse(
      window.localStorage.getItem('kitty.builder-proposal.work.pending') as string,
    )
    expect(checkpoint).toMatchObject({
      version: 1,
      state: 'pending',
      missionId: preparedProposal.mission_id,
      approval: {
        expected_manifest_sha: preparedProposal.manifest_sha256,
        approval_nonce: preparedProposal.approval_nonce,
        confirmed: true,
      },
    })
  })

  it('retains the exact checkpoint after a repeated Mission binding reconciliation failure', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: preparedProposal.mission_id, state: 'active' },
      current_work: { state: 'queued' },
      awaiting_acceptance: true,
      awaiting_acceptance_because: 'Expected Gateway Mission binding is missing',
      mission_acceptance: {
        state: 'unavailable',
        error: `Expected Gateway Mission binding is missing for Builder initiative ${preparedProposal.mission_id}`,
      },
    })

    const first = renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={1}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledOnce())
    first.unmount()

    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({
      ok: false,
      state: 'recovery_required',
      error_code: 'mission_binding_failed',
      mission_id: preparedProposal.mission_id,
    })
    renderWithQueryClient(
      <BuilderProposalCard
        task={task}
        chatId="work-builder-request"
        messageIndex={2}
        recoveryStorageKey="kitty.builder-proposal.work.pending"
        persistResolvedMission={false}
      />,
    )

    const retry = await screen.findByRole('button', { name: 'Retry same approval' })
    fireEvent.click(retry)
    await waitFor(() => expect(gateway.approveBuilderJob).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('button', { name: 'Retry same approval' })).toBeInTheDocument()
    expect(JSON.parse(window.localStorage.getItem('kitty.builder-proposal.work.pending') as string)).toMatchObject({
      state: 'pending',
      missionId: preparedProposal.mission_id,
      approval: {
        expected_manifest_sha: preparedProposal.manifest_sha256,
        approval_nonce: preparedProposal.approval_nonce,
        confirmed: true,
      },
    })
  })

  it('renders a rejected outcome as rejected instead of nobody-has-accepted', async () => {
    window.localStorage.setItem(
      'kitty.builder-proposal.chat-rejected.0',
      preparedProposal.mission_id as string,
    )
    vi.mocked(gateway.resumeBuilderJob).mockResolvedValue({
      ok: true,
      mission: { id: preparedProposal.mission_id, state: 'complete' },
      current_work: { state: 'completed' },
      builder_task_complete: true,
      awaiting_acceptance: true,
      awaiting_acceptance_because: 'the Mission outcome is rejected, not accepted',
      mission_acceptance: { state: 'rejected', reviewer_id: 'reviewer-1', error: null },
    })

    renderWithQueryClient(
      <BuilderProposalCard task={task} chatId="chat-rejected" messageIndex={0} />,
    )

    const status = await screen.findByTestId('builder-job-awaiting-acceptance')
    expect(status).toHaveTextContent(/rejected/i)
    expect(status).not.toHaveTextContent(/Nobody has accepted the result yet/)
  })

})
