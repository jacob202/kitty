import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Dialog, Sheet } from '../src/components/ui/Dialog'

afterEach(cleanup)

describe('overlay primitives', () => {
  it('gives Dialog a 44px close target and moves focus inside', () => {
    render(<Dialog open onClose={vi.fn()} title="Details"><button type="button">Body action</button></Dialog>)
    const close = screen.getByRole('button', { name: 'Close' })
    expect(close).toHaveStyle({ width: '44px', height: '44px' })
    expect(close).toHaveFocus()
  })

  it('gives Sheet the same focus and touch contract', () => {
    render(<Sheet open onClose={vi.fn()} title="Activity"><button type="button">Body action</button></Sheet>)
    const close = screen.getByRole('button', { name: 'Close' })
    expect(close).toHaveStyle({ width: '44px', height: '44px' })
    expect(close).toHaveFocus()
  })
})
