import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { WhatChanged } from '../src/components/WhatChanged'
import type { GatewayStateChange, GatewaySignal } from '../src/lib/gateway'

describe('WhatChanged', () => {
  afterEach(cleanup)

  it('prompts to start tracking when there is no baseline yet', () => {
    render(
      <WhatChanged
        changes={[]}
        newSignals={[]}
        note="no snapshot yet — POST /state/snapshot to create a baseline"
        hasBaseline={false}
        error={null}
        onSnapshot={() => {}}
      />
    )
    expect(screen.getByText(/no snapshot yet/)).toBeInTheDocument()
    expect(screen.getByText('start tracking')).toBeInTheDocument()
  })

  it('calls onSnapshot when the action button is clicked', () => {
    const onSnapshot = vi.fn()
    render(
      <WhatChanged
        changes={[]}
        newSignals={[]}
        hasBaseline={true}
        error={null}
        onSnapshot={onSnapshot}
      />
    )
    fireEvent.click(screen.getByText('mark point'))
    expect(onSnapshot).toHaveBeenCalled()
  })

  it('shows an honest empty state when there is a baseline but nothing changed', () => {
    render(
      <WhatChanged
        changes={[]}
        newSignals={[]}
        hasBaseline={true}
        error={null}
        onSnapshot={() => {}}
      />
    )
    expect(screen.getByText('No changes since the last snapshot.')).toBeInTheDocument()
  })

  it('renders diffed changes and new signals', () => {
    const changes: GatewayStateChange[] = [
      { section: 'todos', field: 'open_count', before: 3, after: 5 },
    ]
    const signals: GatewaySignal[] = [
      {
        id: 1,
        ts: 0,
        source: 'gmail',
        kind: 'new_mail',
        payload: {},
        dedupe_key: null,
        processed_at: null,
        created_at: 0,
      },
    ]
    render(
      <WhatChanged
        changes={changes}
        newSignals={signals}
        hasBaseline={true}
        error={null}
        onSnapshot={() => {}}
      />
    )
    expect(screen.getByText(/todos.open_count: 3 → 5/)).toBeInTheDocument()
    expect(screen.getByText(/new_mail · gmail/)).toBeInTheDocument()
  })

  it('shows an honest error state when the gateway is down instead of a spinner', () => {
    render(
      <WhatChanged
        changes={[]}
        newSignals={[]}
        hasBaseline={true}
        error="Could not reach the gateway"
        onSnapshot={() => {}}
      />
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Could not reach the gateway')
  })
})
