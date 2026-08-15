import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BuilderSurface } from '../src/components/BuilderSurface'
import type {
  BuilderFailureKind,
  BuilderPacketStatus,
  BuilderStatusSnapshot,
  RuntimeFact,
} from '../src/lib/gateway'

// Mutable hook state so tests can drive pending / rejected / accepted states.
const operatorCommand = vi.hoisted(() => ({
  isPending: false,
  isError: false,
  error: null as Error | null,
  mutate: vi.fn(),
}))

vi.mock('../src/lib/queries', () => ({
  useGatewayRuntimeManifest: vi.fn(),
  useOperatorCommand: vi.fn(() => operatorCommand),
}))

const NOW = '2026-07-17T03:00:00Z'

afterEach(() => {
  cleanup()
  operatorCommand.mutate.mockReset()
  operatorCommand.isPending = false
  operatorCommand.isError = false
  operatorCommand.error = null
})

function builderFact(
  value: BuilderStatusSnapshot,
  validUntil = '2099-07-17T03:05:00Z',
): RuntimeFact<BuilderStatusSnapshot> {
  return {
    state: 'available',
    value,
    source: 'builder_status',
    observed_at: NOW,
    valid_until: validUntil,
  }
}

const PACKET: BuilderPacketStatus = {
  initiative_id: 'builder-ui-test',
  packet_id: 'BUILDER-UI-1',
  title: 'Expose truthful Builder status',
  objective: 'Make Builder failures understandable without opening raw logs.',
  task_id: 'task-1',
  task_state: 'blocked',
  depends_on: ['BUILDER-FOUNDATION'],
  eligibility: { state: 'blocked', blocked_by: ['BUILDER-FOUNDATION'] },
  budget: { used: 1, max: 2, exhausted: false },
  attempt_count: 2,
  attempt_history_truncated: false,
  attempt_history: [
    {
      id: 2,
      number: 2,
      outcome: null,
      counts_toward_budget: false,
      implementation_status: null,
      validation_status: null,
      review_verdict: null,
      implementation: null,
      validation: null,
      review: null,
      lease_id: 7,
      created_at: NOW,
      updated_at: NOW,
      data_quality: { state: 'complete', issues: [] },
    },
    {
      id: 1,
      number: 1,
      outcome: 'failed',
      counts_toward_budget: true,
      implementation_status: 'completed',
      validation_status: 'failed',
      review_verdict: 'reject',
      implementation: {
        status: 'completed',
        summary: 'Implemented the status projection.',
        diff_summary: 'Added bounded evidence fields.',
      },
      validation: {
        status: 'failed',
        command_count: 2,
        failed_command_count: 1,
        summary: '1 validation command failed (exit 1).',
      },
      review: {
        verdict: 'reject',
        summary: 'Evidence needs another look.',
        findings: [{ severity: 'major', note: 'The failure reason was unclear.' }],
        findings_truncated: false,
      },
      lease_id: null,
      created_at: '2026-07-17T02:00:00Z',
      updated_at: '2026-07-17T02:10:00Z',
      data_quality: { state: 'complete', issues: [] },
    },
  ],
  lease: {
    id: 7,
    worker_id: 'worker-status',
    branch: 'feat/status-surface',
    base_sha: 'a'.repeat(40),
    created_at: NOW,
  },
  run: {
    id: 'run-1',
    state: 'failed',
    started_at: '2026-07-17T02:58:00Z',
    last_heartbeat_at: NOW,
    ended_at: NOW,
    exit_code: 1,
    updated_at: NOW,
  },
  publication: {
    pr_number: 182,
    pr_url: 'https://github.com/jacob202/kitty/pull/182',
    head_sha: 'b'.repeat(40),
    checks_state: 'failure',
    review_state: 'changes_requested',
    merged: false,
    merged_at: null,
    updated_at: NOW,
  },
  last_event: {
    id: 10,
    type: 'infrastructure_failed',
    created_at: NOW,
    reason: 'worker exited before validation',
    counts_toward_budget: false,
  },
  failure_kind: 'infrastructure',
  blocked_reason: 'worker failed',
  last_error: 'worker exited before validation',
  updated_at: NOW,
  base_sha: 'a'.repeat(40),
  data_quality: { state: 'complete', issues: [] },
  investigation: {
    logs: { state: 'unavailable', reason: 'Safe bounded log delivery is not available yet.' },
    artifacts: { state: 'unavailable', reason: 'Safe durable artifact delivery is not available yet.' },
  },
}

const SNAPSHOT: BuilderStatusSnapshot = {
  schema_version: 2,
  attempt_history_limit: 10,
  integrity: { state: 'complete', partial_packets: 0, total_packets: 1 },
  queue: {
    total: 1,
    queued: 0,
    claimed: 0,
    running: 0,
    blocked: 1,
    pr_opened: 0,
    awaiting_review: 0,
    done: 0,
    failed: 0,
    cancelled: 0,
  },
  initiatives: [
    {
      initiative_id: 'builder-ui-test',
      title: 'Builder UI test initiative',
      state: 'failed',
      pause_reason: null,
      next_packet: null,
      counts: {
        total: 1,
        queued: 0,
        claimed: 0,
        running: 0,
        blocked: 1,
        pr_opened: 0,
        awaiting_review: 0,
        done: 0,
        failed: 0,
        cancelled: 0,
        exhausted: 0,
      },
      data_quality: { state: 'complete', partial_packets: 0 },
      created_at: NOW,
      updated_at: NOW,
      packets: [PACKET],
    },
  ],
}

describe('BuilderSurface', () => {
  it('renders overview, timeline, evidence, publication, and honest investigation states', async () => {
    render(<BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} onBack={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Builder' })).toBeInTheDocument()
    expect(screen.getByText('1 needs attention')).toBeInTheDocument()
    expect(screen.getByText('Builder UI test initiative')).toBeInTheDocument()
    expect(screen.getByText('Expose truthful Builder status')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))

    const heading = screen.getByRole('heading', { name: 'Expose truthful Builder status' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(screen.getByText(PACKET.objective!)).toBeInTheDocument()
    expect(screen.getByText('Infrastructure failure')).toBeInTheDocument()
    expect(screen.getByText('Attempt #2')).toBeInTheDocument()
    expect(screen.getByText('Attempt #1')).toBeInTheDocument()
    expect(screen.getByText('Consumed retry budget')).toBeInTheDocument()
    expect(screen.getByText('1 validation command failed (exit 1).')).toBeInTheDocument()
    expect(screen.getByText('Evidence needs another look.')).toBeInTheDocument()
    expect(screen.getByText('The failure reason was unclear.')).toBeInTheDocument()
    expect(screen.getByText('checks: failure')).toBeInTheDocument()
    expect(screen.getByText('review: changes requested')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open pull request #182' })).toHaveAttribute(
      'href',
      'https://github.com/jacob202/kitty/pull/182',
    )
    expect(screen.getByText('Safe bounded log delivery is not available yet.')).toBeInTheDocument()
    expect(screen.getByText('Safe durable artifact delivery is not available yet.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Back to overview' }))
    await waitFor(() => expect(
      screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }),
    ).toHaveFocus())
  })

  it('keeps loading, empty, degraded, unavailable, and stale states distinct', () => {
    const { rerender } = render(<BuilderSurface fact={undefined} isLoading={true} />)
    expect(screen.getByLabelText('Loading Builder status')).toBeInTheDocument()

    rerender(
      <BuilderSurface
        fact={builderFact({
          ...SNAPSHOT,
          integrity: { state: 'complete', partial_packets: 0, total_packets: 0 },
          queue: { ...SNAPSHOT.queue, total: 0, blocked: 0 },
          initiatives: [],
        })}
        isLoading={false}
      />,
    )
    expect(screen.getByText('No Builder work is recorded yet.')).toBeInTheDocument()

    rerender(
      <BuilderSurface
        fact={{
          ...builderFact({
            ...SNAPSHOT,
            integrity: { state: 'partial', partial_packets: 1, total_packets: 1 },
          }),
          state: 'degraded',
          reason: 'Builder status includes 1 partial packet record.',
        }}
        isLoading={false}
      />,
    )
    expect(screen.getByText('Builder status includes 1 partial packet record.')).toBeInTheDocument()
    expect(screen.getByText('Builder UI test initiative')).toBeInTheDocument()

    rerender(
      <BuilderSurface
        fact={{
          state: 'unavailable',
          value: null,
          source: 'builder_status',
          observed_at: NOW,
          valid_until: NOW,
          reason: 'Builder queue is disabled',
        }}
        isLoading={false}
      />,
    )
    expect(screen.getByText('Builder unavailable')).toBeInTheDocument()
    expect(screen.getByText('Builder queue is disabled')).toBeInTheDocument()

    rerender(
      <BuilderSurface
        fact={builderFact(SNAPSHOT, '2020-01-01T00:00:00Z')}
        isLoading={false}
      />,
    )
    expect(screen.getByText(/Data may be stale/)).toBeInTheDocument()
  })

  it('orders attention before healthy packets without losing initiative grouping', () => {
    const healthy: BuilderPacketStatus = {
      ...PACKET,
      packet_id: 'HEALTHY',
      title: 'Healthy packet',
      task_state: 'done',
      failure_kind: null,
      blocked_reason: null,
      last_error: null,
      budget: { used: 0, max: 2, exhausted: false },
      eligibility: { state: 'not_queued', blocked_by: [] },
    }
    const snapshot = {
      ...SNAPSHOT,
      initiatives: [{ ...SNAPSHOT.initiatives[0], packets: [healthy, PACKET] }],
    }

    render(<BuilderSurface fact={builderFact(snapshot)} isLoading={false} />)

    const packetButtons = screen.getAllByRole('button', { name: /^View packet/ })
    expect(packetButtons.map((button) => button.getAttribute('aria-label'))).toEqual([
      'View packet Expose truthful Builder status',
      'View packet Healthy packet',
    ])
  })

  it('shows the deterministic next action and opens an accessible all-packets modal', async () => {
    render(<BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} />)

    expect(screen.getByLabelText('Builder next action')).toHaveTextContent(
      'Investigate: Expose truthful Builder status',
    )
    expect(screen.getByText('worker failed')).toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: 'View all packets' })
    fireEvent.click(trigger)

    const dialog = screen.getByRole('dialog', { name: 'All Builder packets' })
    expect(dialog).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'All Builder packets' })).toHaveFocus())
    expect(screen.getByRole('button', {
      name: 'Open packet Expose truthful Builder status from all packets',
    })).toBeInTheDocument()

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('explains when a packet is ready without implying the UI can run it', () => {
    const readyPacket: BuilderPacketStatus = {
      ...PACKET,
      task_state: 'queued',
      eligibility: { state: 'eligible', blocked_by: [] },
      failure_kind: null,
      blocked_reason: null,
      last_error: null,
      run: null,
    }
    const readySnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      queue: { ...SNAPSHOT.queue, queued: 1, blocked: 0 },
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        state: 'active',
        next_packet: readyPacket.packet_id,
        counts: { ...SNAPSHOT.initiatives[0].counts, queued: 1, blocked: 0 },
        packets: [readyPacket],
      }],
    }

    render(<BuilderSurface fact={builderFact(readySnapshot)} isLoading={false} />)

    expect(screen.getByLabelText('Builder next action')).toHaveTextContent(
      'Ready for an authorized run: BUILDER-UI-1',
    )
    expect(screen.getByText(/This UI does not start Builder work/)).toBeInTheDocument()
  })

  it('opens a Retry this work preview for the selected packet and sends no mutation until confirm', () => {
    const deadSnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        packets: [{ ...PACKET, task_state: 'failed' }],
      }],
    }

    render(<BuilderSurface fact={builderFact(deadSnapshot)} isLoading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))

    // First click opens the inline approval preview for the exact selected
    // packet and sends no mutation.
    fireEvent.click(screen.getByRole('button', { name: 'Retry this work' }))
    const preview = screen.getByLabelText('Retry this work preview')
    expect(preview).toBeInTheDocument()
    expect(preview).toHaveTextContent(PACKET.initiative_id)
    expect(preview).toHaveTextContent(PACKET.packet_id)
    expect(operatorCommand.mutate).not.toHaveBeenCalled()

    // Cancel closes the preview and still sends no mutation.
    fireEvent.click(screen.getByRole('button', { name: 'Cancel retry' }))
    expect(screen.queryByLabelText('Retry this work preview')).toBeNull()
    expect(operatorCommand.mutate).not.toHaveBeenCalled()

    // Reopening the preview still sends nothing.
    fireEvent.click(screen.getByRole('button', { name: 'Retry this work' }))
    expect(screen.getByLabelText('Retry this work preview')).toBeInTheDocument()
    expect(operatorCommand.mutate).not.toHaveBeenCalled()
  })

  it('sends exactly one requeue action with the selected initiative and packet on Confirm retry', () => {
    const deadSnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        packets: [{ ...PACKET, task_state: 'failed' }],
      }],
    }

    render(<BuilderSurface fact={builderFact(deadSnapshot)} isLoading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))
    fireEvent.click(screen.getByRole('button', { name: 'Retry this work' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm retry' }))

    expect(operatorCommand.mutate).toHaveBeenCalledTimes(1)
    expect(operatorCommand.mutate).toHaveBeenCalledWith(
      {
        action: 'requeue',
        initiative_id: PACKET.initiative_id,
        packet_id: PACKET.packet_id,
        task_id: PACKET.task_id,
        reason: 'Builder surface requested retry of selected packet',
      },
      expect.anything(),
    )
  })

  it('surfaces a rejected Builder action as visible failure and never completion', () => {
    operatorCommand.mutate.mockImplementation((_payload, options) => {
      const error = new Error('task not found: requeue rejected')
      options?.onError?.(error, _payload, undefined)
      options?.onSettled?.(undefined, error, _payload, undefined)
    })
    operatorCommand.isError = true
    operatorCommand.error = new Error('task not found: requeue rejected')
    const deadSnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        packets: [{ ...PACKET, task_state: 'failed' }],
      }],
    }

    render(<BuilderSurface fact={builderFact(deadSnapshot)} isLoading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))
    fireEvent.click(screen.getByRole('button', { name: 'Retry this work' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm retry' }))

    expect(screen.getByText(/task not found: requeue rejected/)).toBeInTheDocument()
    expect(screen.queryByText(/Retry accepted/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Retry this work' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Retry progress')).toBeNull()
  })

  it('shows accepted progress without claiming completion after a confirmed retry', () => {
    operatorCommand.mutate.mockImplementation((_payload, options) => {
      const data = { ok: true, action: 'requeue', task_id: PACKET.task_id, detail: 'task requeued' }
      options?.onSuccess?.(data, _payload, undefined)
      options?.onSettled?.(data, undefined, _payload, undefined)
    })
    const deadSnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        packets: [{ ...PACKET, task_state: 'failed' }],
      }],
    }

    render(<BuilderSurface fact={builderFact(deadSnapshot)} isLoading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))
    fireEvent.click(screen.getByRole('button', { name: 'Retry this work' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm retry' }))

    expect(screen.getByText(/Retry accepted — waiting for the runtime manifest to confirm/)).toBeInTheDocument()
    const progress = screen.getByLabelText('Retry progress')
    const currentStep = progress.querySelector('[aria-current="step"]')
    expect(currentStep).toHaveTextContent('accepted')
    expect(currentStep).not.toHaveTextContent('complete')
  })

  it.each<[BuilderPacketStatus['task_state'], string, Partial<BuilderPacketStatus> | undefined]>([
    ['queued', 'queued', undefined],
    ['running', 'running', { run: { ...PACKET.run!, state: 'running' } }],
    ['running', 'validation', {
      run: { ...PACKET.run!, state: 'running' },
      attempt_history: [{
        ...PACKET.attempt_history[0],
        outcome: null,
        implementation_status: 'completed',
        validation_status: null,
        review_verdict: null,
      }],
    }],
    ['awaiting_review', 'review', undefined],
    ['done', 'complete', undefined],
  ])('derives the %s retry progress phase from durable packet facts', (taskState, phase, overrides) => {
    const packet = { ...PACKET, task_state: taskState, ...overrides }
    const snapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{ ...SNAPSHOT.initiatives[0], packets: [packet] }],
    }

    render(<BuilderSurface fact={builderFact(snapshot)} isLoading={false} />)
    fireEvent.click(screen.getByRole('button', { name: `View packet ${packet.title}` }))

    const progress = screen.getByLabelText('Retry progress')
    const currentStep = progress.querySelector('[aria-current="step"]')
    expect(currentStep).toHaveTextContent(phase)
    if (phase !== 'complete') {
      expect(currentStep).not.toHaveTextContent('complete')
    }
  })

  it('returns a durable failed state after retry to attention and never shows complete', () => {
    operatorCommand.mutate.mockImplementation((_payload, options) => {
      const data = { ok: true, action: 'requeue', task_id: PACKET.task_id, detail: 'task requeued' }
      options?.onSuccess?.(data, _payload, undefined)
      options?.onSettled?.(data, undefined, _payload, undefined)
    })
    const failedSnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        packets: [{ ...PACKET, task_state: 'failed' }],
      }],
    }
    const { rerender } = render(<BuilderSurface fact={builderFact(failedSnapshot)} isLoading={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))
    fireEvent.click(screen.getByRole('button', { name: 'Retry this work' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm retry' }))
    expect(screen.getByLabelText('Retry progress')).toHaveTextContent('accepted')

    // The refreshed manifest reports the packet durably failed again (newer
    // updated_at). It returns to attention and can never display complete.
    rerender(
      <BuilderSurface
        fact={builderFact({
          ...failedSnapshot,
          initiatives: [{
            ...failedSnapshot.initiatives[0],
            packets: [{ ...PACKET, task_state: 'failed', updated_at: '2026-07-17T04:00:00Z' }],
          }],
        })}
        isLoading={false}
      />,
    )

    expect(screen.queryByLabelText('Retry progress')).toBeNull()
    expect(screen.getByRole('button', { name: 'Retry this work' })).toBeInTheDocument()
    // No active phase chip anywhere: the packet cannot display complete after a
    // durable re-failure. (A broad /complete/i text search is wrong here — the
    // attempt history legitimately shows "Implementation · completed".)
    expect(screen.queryByLabelText('Retry progress')).toBeNull()
    expect(document.querySelector('[aria-current="step"]')).toBeNull()
  })

  it('prioritizes a paused initiative reason as the next decision', () => {
    const pausedSnapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [{
        ...SNAPSHOT.initiatives[0],
        state: 'paused',
        pause_reason: 'packet requires scope or identity judgment',
      }],
    }

    render(<BuilderSurface fact={builderFact(pausedSnapshot)} isLoading={false} />)

    expect(screen.getByLabelText('Builder next action')).toHaveTextContent(
      'Needs a decision: Builder UI test initiative',
    )
    // The read-only surface renders the pause reason in the next-action card
    // and the overview. BuilderInitiativeCards prefixes it with "Paused: ", so
    // it does not match the exact-text query. The old count of 3 included the
    // now-removed mutation controls (BuilderControls), which were dropped when
    // the surface became read-only.
    expect(screen.getAllByText('packet requires scope or identity judgment')).toHaveLength(2)
  })

  it.each<[BuilderFailureKind, string]>([
    ['implementation', 'Implementation failure'],
    ['infrastructure', 'Infrastructure failure'],
    ['identity', 'Identity failure'],
    ['scope', 'Scope failure'],
    ['validation', 'Validation failure'],
    ['review', 'Review failure'],
    ['cancelled', 'Cancelled'],
    ['blocked', 'Blocked'],
    ['exhausted', 'Attempt budget exhausted'],
  ])('renders the %s failure category', (kind, label) => {
    const packet = { ...PACKET, failure_kind: kind }
    const snapshot = {
      ...SNAPSHOT,
      initiatives: [{ ...SNAPSHOT.initiatives[0], packets: [packet] }],
    }
    render(<BuilderSurface fact={builderFact(snapshot)} isLoading={false} />)

    fireEvent.click(screen.getByRole('button', { name: `View packet ${packet.title}` }))

    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('reports truncated history instead of implying it is complete', () => {
    const packet = { ...PACKET, attempt_count: 12, attempt_history_truncated: true }
    const snapshot = {
      ...SNAPSHOT,
      initiatives: [{ ...SNAPSHOT.initiatives[0], packets: [packet] }],
    }
    render(<BuilderSurface fact={builderFact(snapshot)} isLoading={false} />)

    fireEvent.click(screen.getByRole('button', { name: `View packet ${packet.title}` }))

    expect(screen.getByText('Showing latest 2 of 12 attempts.')).toBeInTheDocument()
  })

  it('uses initiative plus packet identity when packet ids collide', () => {
    const secondPacket: BuilderPacketStatus = {
      ...PACKET,
      initiative_id: 'second-initiative',
      title: 'Second packet with same id',
      objective: 'This is the second initiative packet.',
    }
    const snapshot: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      integrity: { state: 'complete', partial_packets: 0, total_packets: 2 },
      initiatives: [
        SNAPSHOT.initiatives[0],
        {
          ...SNAPSHOT.initiatives[0],
          initiative_id: 'second-initiative',
          title: 'Second initiative',
          packets: [secondPacket],
        },
      ],
    }
    render(<BuilderSurface fact={builderFact(snapshot)} isLoading={false} />)

    fireEvent.click(screen.getByRole('button', { name: 'View packet Second packet with same id' }))

    expect(screen.getByText('This is the second initiative packet.')).toBeInTheDocument()
  })

  it('keeps an open packet detail synchronized with the next bounded manifest poll', () => {
    const { rerender } = render(
      <BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }),
    )

    const refreshed: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [
        {
          ...SNAPSHOT.initiatives[0],
          packets: [{ ...PACKET, last_error: 'worker recovered after reconnect' }],
        },
      ],
    }
    rerender(<BuilderSurface fact={builderFact(refreshed)} isLoading={false} />)

    expect(screen.getByText('worker recovered after reconnect')).toBeInTheDocument()
  })

  it('does not render unsupported mutation controls', () => {
    render(<BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} />)

    expect(
      screen.queryByRole('button', { name: /run|retry|cancel|approve|reject|publish|merge/i }),
    ).toBeNull()
  })
})
