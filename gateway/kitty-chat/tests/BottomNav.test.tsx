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
    expect(screen.getByLabelText('Library')).toBeDefined()
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

  it('renders as a navigation landmark', () => {
    render(<BottomNav activeView="home" onViewChange={onViewChange} />)
    expect(screen.getByRole('navigation')).toBeDefined()
  })
})
