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


describe('SessionSidebar visual hierarchy', () => {
  afterEach(cleanup)

  const chats: Chat[] = [{
    id: 'chat-active',
    title: 'Active Chat',
    messages: [{ role: 'user', content: 'hello', timestamp: new Date() }],
    model: 'kitty-default',
    color: 'teal',
    createdAt: new Date(),
    updatedAt: new Date(),
  }]

  it('keeps New chat useful without making it a primary-accent banner', () => {
    render(<SessionSidebar chats={chats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    const button = screen.getByRole('button', { name: /new chat/i })
    const style = button.getAttribute('style') ?? ''
    expect(style).toContain('background: var(--color-selected)')
    expect(style).toContain('color: var(--color-accent)')
    expect(style).toContain('border: 1px solid var(--color-separator)')
  })

  it('uses the shared selected state for the active conversation', () => {
    render(<SessionSidebar chats={chats} activeChatId="chat-active" onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    const active = screen.getByRole('button', { name: /Active Chat/ })
    expect(active.getAttribute('style') ?? '').toContain('background: var(--color-selected)')
  })
})
