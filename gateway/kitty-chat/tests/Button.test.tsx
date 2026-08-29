import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Button } from '../src/components/ui/Button'

afterEach(() => cleanup())

describe('Button', () => {
  it('uses semantic design tokens for persistent variants', () => {
    render(
      <>
        <Button>Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="danger">Danger</Button>
      </>,
    )

    expect(screen.getByRole('button', { name: 'Primary' })).toHaveStyle({ background: 'var(--color-accent)' })
    expect(screen.getByRole('button', { name: 'Secondary' })).toHaveStyle({ background: 'var(--color-surface)' })
    expect(screen.getByRole('button', { name: 'Danger' })).toHaveStyle({ color: 'var(--color-destructive)' })
  })

  it('keeps the default action touch sized', () => {
    render(<Button>Save</Button>)
    expect(screen.getByRole('button', { name: 'Save' })).toHaveStyle({ minHeight: '44px' })
  })
})
