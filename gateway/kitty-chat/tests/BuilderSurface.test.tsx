import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BuilderSurface } from '../src/components/BuilderSurface'
import type { BuilderStatusSnapshot, RuntimeFact } from '../src/lib/gateway'


const NOW = '2026-07-17T03:00:00Z'

afterEach(cleanup)

function builderFact(value: BuilderStatusSnapshot, validUntil = '2026-07-17T03:05:00Z'):
  RuntimeFact<BuilderStatusSnapshot> {
  return {
    state: 'available',
    value,
    source: 'builder_status',
    observed_at: NOW,
    valid_until: validUntil,
  }
}

const SNAPSHOT: BuilderStatusSnapshot = {
  schema_version: 1,
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
      created_at: NOW,
      updated_at: NOW,
      packets: [
        {
          packet_id: 'BUILDER-UI-1',
          title: 'Expose truthful Builder status',
          task_id: 'task-1',
          task_state: 'blocked',
          depends_on: [],
          eligibility: { state: 'not_queued', blocked_by: [] },
          budget: { used: 1, max: 2, exhausted: false },
          attempt: {
            id: 2,
            number: 2,
            outcome: 'failed',
            implementation_status: 'completed',
            validation_status: 'failed',
            review_verdict: 'reject',
            lease_id: null,
            created_at: NOW,
            updated_at: NOW,
          },
          previous_attempt: null,
          lease: null,
          run: {
            id: 'run-1',
            state: 'failed',
            started_at: NOW,
            last_heartbeat_at: NOW,
            ended_at: NOW,
            exit_code: 1,
          },
          publication: null,
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
        },
      ],
    },
  ],
}

describe('BuilderSurface', () => {
  it('renders the overview and packet detail from the durable projection', () => {
    render(<BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} onBack={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Builder' })).toBeInTheDocument()
    expect(screen.getByText('1 needs attention')).toBeInTheDocument()
    expect(screen.getByText('Builder UI test initiative')).toBeInTheDocument()
    expect(screen.getByText('Expose truthful Builder status')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))

    expect(screen.getByRole('heading', { name: 'Expose truthful Builder status' })).toBeInTheDocument()
    expect(screen.getByText('Infrastructure failure')).toBeInTheDocument()
    expect(screen.getByText('Review rejected')).toBeInTheDocument()
    expect(screen.getByText('Attempt history')).toBeInTheDocument()
    expect(screen.getByText('worker exited before validation')).toBeInTheDocument()
  })

  it('keeps loading, empty, unavailable, and stale states honest', () => {
    const { rerender } = render(<BuilderSurface fact={undefined} isLoading={true} />)
    expect(screen.getByLabelText('Loading Builder status')).toBeInTheDocument()

    rerender(
      <BuilderSurface
        fact={builderFact({ ...SNAPSHOT, queue: { ...SNAPSHOT.queue, total: 0 }, initiatives: [] })}
        isLoading={false}
      />,
    )
    expect(screen.getByText('No Builder work is recorded yet.')).toBeInTheDocument()

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

    rerender(<BuilderSurface fact={builderFact(SNAPSHOT, '2020-01-01T00:00:00Z')} isLoading={false} />)
    expect(screen.getByText(/Data may be stale/)).toBeInTheDocument()
  })

  it('does not render unsupported mutation controls', () => {
    render(<BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} />)

    expect(screen.queryByRole('button', { name: /run|retry|cancel|approve|publish|merge/i })).toBeNull()
  })

  it('keeps an open packet detail synchronized with the next bounded manifest poll', () => {
    const { rerender } = render(<BuilderSurface fact={builderFact(SNAPSHOT)} isLoading={false} />)

    fireEvent.click(screen.getByRole('button', { name: 'View packet Expose truthful Builder status' }))

    const refreshed: BuilderStatusSnapshot = {
      ...SNAPSHOT,
      initiatives: [
        {
          ...SNAPSHOT.initiatives[0],
          packets: [{ ...SNAPSHOT.initiatives[0].packets[0], last_error: 'worker recovered after reconnect' }],
        },
      ],
    }
    rerender(<BuilderSurface fact={builderFact(refreshed)} isLoading={false} />)

    expect(screen.getByText('worker recovered after reconnect')).toBeInTheDocument()
  })
})
