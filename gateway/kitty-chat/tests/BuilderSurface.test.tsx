import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BuilderSurface } from '../src/components/BuilderSurface'
import type {
  BuilderFailureKind,
  BuilderPacketStatus,
  BuilderStatusSnapshot,
  RuntimeFact,
} from '../src/lib/gateway'

const NOW = '2026-07-17T03:00:00Z'

afterEach(cleanup)

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
