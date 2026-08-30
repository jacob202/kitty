import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BuilderPacketTree } from '../src/components/builder/BuilderPacketTree'

afterEach(cleanup)

const snapshot = {
  initiatives: [{
    initiative_id: 'INIT-1',
    title: 'Readable initiative',
    state: 'active',
    packets: [{
      packet_id: 'PKT-1',
      initiative_id: 'INIT-1',
      title: 'Readable packet title',
      task_state: 'blocked',
      blocked_reason: 'needs review',
      run: null,
    }],
  }],
}

describe('Builder packet tree presentation', () => {
  it('uses readable product typography and touch-sized packet rows', () => {
    render(<BuilderPacketTree snapshot={snapshot as never} onSelect={vi.fn()} />)
    const option = screen.getByRole('option', { name: /readable packet title/i })
    expect(option).toHaveStyle({ minHeight: '44px' })
    expect(option.parentElement?.parentElement).toHaveStyle({ fontFamily: 'var(--font-body)' })
  })
})
