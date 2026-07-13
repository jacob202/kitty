import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, afterEach, vi, beforeEach, type Mock } from 'vitest'
import { SessionSidebar } from '../src/components/SessionSidebar'
import { useActiveProject, useProjectNext, useDeadlines } from '../src/lib/queries'
import type { Chat } from '../src/lib/types'

vi.mock('../src/lib/queries', () => ({
  useActiveProject: vi.fn(),
  useProjectNext: vi.fn(),
  useDeadlines: vi.fn(),
}))

function setDefaultMocks() {
  (useActiveProject as Mock).mockReturnValue({ data: null, isPending: false, isError: false })
  ;(useProjectNext as Mock).mockReturnValue({ data: null, isPending: false, isError: false })
  ;(useDeadlines as Mock).mockReturnValue({ data: { deadlines: [] }, isPending: false, isError: false })
}

describe('SessionSidebar', () => {
  beforeEach(setDefaultMocks)
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

  it('renders new chat button and search input', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByRole('button', { name: '+ new chat' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('search chats')).toBeInTheDocument()
  })

  it('shows today and earlier groups based on date', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByText('today')).toBeInTheDocument()
    expect(screen.getByText('earlier')).toBeInTheDocument()
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
})
