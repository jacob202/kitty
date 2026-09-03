import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BottomNav } from '../src/components/BottomNav'

afterEach(cleanup)

describe('BottomNav', () => {
  const onViewChange = vi.fn()

  it('renders all navigation tabs', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    expect(screen.getByLabelText('Home')).toBeDefined()
    expect(screen.getByLabelText('Chat')).toBeDefined()
    expect(screen.getByLabelText('Work')).toBeDefined()
    expect(screen.getByLabelText('Image Lab')).toBeDefined()
    expect(screen.getByLabelText('Library')).toBeDefined()
    expect(screen.getByLabelText('More')).toBeDefined()
  })

  it('renders exactly the six primary destinations', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(nav.querySelectorAll('button')).toHaveLength(6)
  })

  it('marks active tab with aria-current', () => {
    render(<BottomNav activeView="chat" onViewChange={onViewChange} />)
    expect(screen.getByLabelText('Chat').getAttribute('aria-current')).toBe('page')
    expect(screen.getByLabelText('Home').getAttribute('aria-current')).toBeNull()
  })

  it('calls onViewChange on tab click', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    fireEvent.click(screen.getByLabelText('Chat'))
    expect(onViewChange).toHaveBeenCalledWith('chat')
  })

  it('uses phone-sized touch targets', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    expect(screen.getByLabelText('Home')).toHaveStyle({ minHeight: '44px' })
  })

  it('opens secondary destinations from More without adding a seventh primary tab', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    const more = screen.getByLabelText('More')
    expect(more).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('menu', { name: 'More destinations' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: 'Projects' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: 'Agents' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: 'Automations' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: 'Settings' })).toBeVisible()

    fireEvent.click(screen.getByRole('menuitem', { name: 'Agents' }))
    expect(onViewChange).toHaveBeenCalledWith('agents')
    expect(screen.queryByRole('menu', { name: 'More destinations' })).not.toBeInTheDocument()
  })

  it('routes Research from the mobile More menu', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    fireEvent.click(screen.getByLabelText('More'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Research' }))
    expect(onViewChange).toHaveBeenCalledWith('research')
  })

  it.each(['automations', 'agents', 'research'])('marks More current for %s', (activeView) => {
    render(<BottomNav activeView={activeView} onViewChange={onViewChange} />)
    expect(screen.getByLabelText('More')).toHaveAttribute('aria-current', 'page')
  })

  it('renders as a navigation landmark', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    expect(screen.getByRole('navigation')).toBeDefined()
  })
})
