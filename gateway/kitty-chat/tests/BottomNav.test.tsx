import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BottomNav } from '../src/components/BottomNav'

afterEach(cleanup)

describe('BottomNav', () => {
  const onNavigate = vi.fn()

  it('renders all navigation tabs', () => {
    render(<BottomNav activeView="home" onNavigate={onNavigate} />)
    expect(screen.getByLabelText('home')).toBeDefined()
    expect(screen.getByLabelText('chat')).toBeDefined()
    expect(screen.getByLabelText('create')).toBeDefined()
    expect(screen.getByLabelText('learn')).toBeDefined()
    expect(screen.getByLabelText('work')).toBeDefined()
  })

  it('marks active tab with aria-current', () => {
    render(<BottomNav activeView="chat" onNavigate={onNavigate} />)
    expect(screen.getByLabelText('chat').getAttribute('aria-current')).toBe('page')
    expect(screen.getByLabelText('home').getAttribute('aria-current')).toBeNull()
  })

  it('calls onNavigate on tab click', () => {
    render(<BottomNav activeView="home" onNavigate={onNavigate} />)
    fireEvent.click(screen.getByLabelText('chat'))
    expect(onNavigate).toHaveBeenCalledWith('chat')
  })

  it('renders as a navigation landmark', () => {
    render(<BottomNav activeView="home" onNavigate={onNavigate} />)
    expect(screen.getByRole('navigation')).toBeDefined()
  })
})
