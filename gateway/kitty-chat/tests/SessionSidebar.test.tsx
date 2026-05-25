import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { SessionSidebar } from '../src/components/SessionSidebar'
import type { Chat } from '../src/lib/types'

describe('SessionSidebar', () => {
  afterEach(cleanup)

  const mockChats: Chat[] = [
    {
      id: 'chat-1',
      title: 'First Chat',
      messages: [],
      model: 'kitty-default',
      color: 'teal',
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    {
      id: 'chat-2',
      title: 'Second Chat',
      messages: [{ role: 'user', content: 'hello', timestamp: new Date() }],
      model: 'kitty-default',
      color: 'coral',
      createdAt: new Date(Date.now() - 48 * 3600 * 1000),
      updatedAt: new Date(Date.now() - 48 * 3600 * 1000),
    },
  ]

  it('renders sessions header and new chat button', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByText('sessions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+ new' })).toBeInTheDocument()
  })

  it('shows today and earlier groups based on date', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Earlier')).toBeInTheDocument()
  })

  it('shows chat titles', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByText('First Chat')).toBeInTheDocument()
    expect(screen.getByText('Second Chat')).toBeInTheDocument()
  })

  it('calls onSelectChat when session clicked', () => {
    const onSelect = vi.fn()
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={onSelect} onNewChat={() => {}} onCloseChat={() => {}} />)
    fireEvent.click(screen.getByText('First Chat'))
    expect(onSelect).toHaveBeenCalledWith('chat-1')
  })

  it('shows close button only on hover for non-collapsed', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    const closeButtons = screen.getAllByText('✕')
    expect(closeButtons.length).toBe(mockChats.length)
  })

  it('collapses to icon-only mode when collapsed prop is true', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} collapsed={true} />)
    expect(screen.queryByText('sessions')).not.toBeInTheDocument()
    expect(screen.queryByText('Today')).not.toBeInTheDocument()
    expect(screen.queryByText('First Chat')).not.toBeInTheDocument()
    expect(screen.getByTitle('First Chat')).toBeInTheDocument()
    expect(screen.getByTitle('Second Chat')).toBeInTheDocument()
  })

  it('new chat button shows + only when collapsed', () => {
    const { rerender } = render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} collapsed={false} />)
    expect(screen.getByText('+ new')).toBeInTheDocument()

    rerender(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} collapsed={true} />)
    expect(screen.queryByText('+ new')).not.toBeInTheDocument()
    expect(screen.getByText('+')).toBeInTheDocument()
  })
})
