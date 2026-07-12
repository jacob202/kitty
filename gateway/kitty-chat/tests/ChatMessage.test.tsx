import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { ChatMessage } from '../src/components/ChatMessage'
import type { Message } from '../src/lib/types'

const kittyMsg: Message = {
  id: 'm1',
  role: 'assistant',
  content: 'hi. i checked the thing.',
  timestamp: new Date(),
}

describe('ChatMessage actions', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  function renderMessage(message: Message = kittyMsg, props: Partial<React.ComponentProps<typeof ChatMessage>> = {}) {
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    return render(
      <QueryClientProvider client={queryClient}>
        <ChatMessage message={message} chatId="chat-123" messageIndex={2} {...props} />
      </QueryClientProvider>
    )
  }

  it('shows copy and retry for a finished kitty message with onRetry', () => {
    const onRetry = vi.fn()
    renderMessage(kittyMsg, { onRetry })
    expect(screen.getByTitle('copy message')).toBeInTheDocument()
    fireEvent.click(screen.getByTitle('regenerate this reply'))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('hides retry when onRetry is not provided', () => {
    renderMessage()
    expect(screen.queryByTitle('regenerate this reply')).not.toBeInTheDocument()
  })

  it('shows no actions while streaming', () => {
    renderMessage({ ...kittyMsg, content: '' }, { isStreaming: true })
    expect(screen.queryByTitle('copy message')).not.toBeInTheDocument()
  })

  it('shows no actions on user messages', () => {
    renderMessage({ ...kittyMsg, role: 'user' }, { onRetry: vi.fn() })
    expect(screen.queryByTitle('copy message')).not.toBeInTheDocument()
  })

  it('submits assistant feedback with its chat and message identifiers', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )
    renderMessage()

    fireEvent.click(screen.getByRole('button', { name: 'rate this response helpful' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/proxy/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: 'chat-123', message_index: 2, rating: 'up' }),
        signal: expect.any(AbortSignal),
      })
    })
  })

  it('reveals actions on keyboard focus and gives them 44px targets', () => {
    renderMessage()

    const helpfulButton = screen.getByRole('button', { name: 'rate this response helpful' })
    fireEvent.focus(helpfulButton)

    expect(helpfulButton.parentElement).toHaveStyle({ opacity: '1' })
    expect(helpfulButton).toHaveStyle({ minWidth: '44px', minHeight: '44px' })
  })

  it('keeps actions visible on compact (touch) layout without hover or focus', () => {
    renderMessage(kittyMsg, { compact: true })
    const helpfulButton = screen.getByRole('button', { name: 'rate this response helpful' })
    expect(helpfulButton.parentElement).toHaveStyle({ opacity: '1' })
  })

  it('hides actions when compact but still streaming', () => {
    renderMessage({ ...kittyMsg, content: '' }, { compact: true, isStreaming: true })
    expect(screen.queryByTitle('copy message')).not.toBeInTheDocument()
  })

  it('shows who answered via the producing model', () => {
    renderMessage({ ...kittyMsg, model: 'sonnet-4', content: 'checked it.' })
    expect(screen.getByText(/answered by sonnet-4/)).toBeInTheDocument()
  })

  it('surfaces council routing as expert chips', () => {
    renderMessage({
      ...kittyMsg,
      model: 'opus-4',
      content: 'done.',
      routing: [
        { task_id: 't1', category: 'research', agent: 'researcher', priority: 1 },
        { task_id: 't2', category: 'writing', agent: 'writer', priority: 2 },
      ],
    })
    expect(screen.getByText(/answered by opus-4/)).toBeInTheDocument()
    expect(screen.getByTitle('research · priority 1')).toHaveTextContent('researcher · p1')
    expect(screen.getByTitle('writing · priority 2')).toHaveTextContent('writer · p2')
  })

  it('does not show attribution for user messages', () => {
    renderMessage({ ...kittyMsg, role: 'user', model: 'sonnet-4' })
    expect(screen.queryByText(/answered by/)).not.toBeInTheDocument()
  })

  it('does not show attribution while the reply is still streaming', () => {
    renderMessage({ ...kittyMsg, model: 'sonnet-4', content: 'partial…' }, { isStreaming: true })
    expect(screen.queryByText(/answered by/)).not.toBeInTheDocument()
  })

  it('shows a feedback error when the gateway rejects the rating', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 503, statusText: 'Service Unavailable' }))
    renderMessage()

    fireEvent.click(screen.getByRole('button', { name: 'rate this response unhelpful' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'feedback failed: Gateway returned 503 Service Unavailable',
    )
  })
})
