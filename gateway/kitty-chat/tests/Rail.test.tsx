import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { Rail } from '../src/components/Rail'

afterEach(cleanup)

describe('Rail', () => {
  it('uses product-facing navigation language and exposes the active location', () => {
    render(<Rail activeView="studio" />)

    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Home' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Chat' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Work' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Projects' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Library' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Automations' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument()

    const imageLab = screen.getByRole('button', { name: 'Image Lab' })
    expect(imageLab).toHaveAttribute('aria-current', 'page')
  })

  it('gives the appearance control an accessible name', () => {
    render(<Rail activeView="home" onToggleTheme={() => {}} />)
    expect(screen.getByRole('button', { name: 'Switch appearance' })).toBeInTheDocument()
  })
})
