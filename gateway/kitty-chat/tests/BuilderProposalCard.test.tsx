import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { BuilderProposalCard } from '../src/components/builder/BuilderProposalCard'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    proposeBuilderJob: vi.fn(),
    approveBuilderJob: vi.fn(),
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

describe('BuilderProposalCard', () => {
  afterEach(cleanup)

  it('does not create a job merely by rendering the proposal', () => {
    renderWithQueryClient(<BuilderProposalCard task={task} />)

    expect(screen.getAllByText(/Fix the flaky retry loop/).length).toBeGreaterThan(0)
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
    expect(gateway.approveBuilderJob).not.toHaveBeenCalled()
  })

  it('flags a malformed proposal without calling propose', () => {
    renderWithQueryClient(
      <BuilderProposalCard task={{ objective: '', instructions: '', allowed_paths: [] }} />,
    )

    expect(screen.getByText(/Malformed Builder proposal/)).toBeInTheDocument()
    expect(gateway.proposeBuilderJob).not.toHaveBeenCalled()
  })

  it('compiles the task, then requires a confirm step before approving', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({
      ok: true,
      state: 'accepted',
      mission_id: preparedProposal.mission_id,
    })

    renderWithQueryClient(<BuilderProposalCard task={task} />)

    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    await waitFor(() => expect(gateway.proposeBuilderJob).toHaveBeenCalledOnce())
    expect(gateway.proposeBuilderJob).toHaveBeenCalledWith(
      expect.objectContaining({ objective: task.objective, allowed_paths: task.allowed_paths }),
      expect.anything(),
    )

    const approveButton = await screen.findByText('Approve')
    fireEvent.click(approveButton)

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
    await screen.findByText(/Builder job created/)
  })

  it('surfaces a refused approval instead of a false success', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockResolvedValue(preparedProposal)
    vi.mocked(gateway.approveBuilderJob).mockResolvedValue({
      ok: false,
      state: 'needs_decision',
      error: 'Builder base moved; prepare a new Mission version.',
    })

    renderWithQueryClient(<BuilderProposalCard task={task} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))
    fireEvent.click(await screen.findByText('Approve'))
    fireEvent.click(screen.getByText('Confirm'))

    await screen.findByText(/Builder base moved/)
    expect(screen.queryByText(/Builder job created/)).not.toBeInTheDocument()
  })

  it('translates an unreachable gateway into a plain-language message, not the raw browser error', async () => {
    vi.mocked(gateway.proposeBuilderJob).mockRejectedValue(new TypeError('Failed to fetch'))

    renderWithQueryClient(<BuilderProposalCard task={task} />)
    fireEvent.click(screen.getByText('Compile as Builder Mission'))

    await screen.findByText(/Could not reach the Kitty gateway/)
    expect(screen.queryByText('Failed to fetch')).not.toBeInTheDocument()
  })
})
