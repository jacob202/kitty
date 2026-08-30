import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { ChatMessage, FORGET_GRACE_MS } from '../src/components/ChatMessage'
import type { Message } from '../src/lib/types'

const deleteMemory = vi.hoisted(() => vi.fn())
vi.mock('../src/lib/gateway', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  deleteMemory,
}))

const msgWithMemories: Message = {
  id: 'm1',
  role: 'assistant',
  content: 'noted.',
  timestamp: new Date(),
  memoryItems: [
    { text: 'Jacob drives a 2010 Civic', memoryId: 'mem-1' },
    { text: 'a knowledge chunk with no id' },
  ],
}

function renderMessage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatMessage message={msgWithMemories} chatId="chat-1" messageIndex={0} />
    </QueryClientProvider>,
  )
}

function openBlock() {
  fireEvent.click(screen.getByText(/kitty remembered/))
}

describe('CR-06 memory forget with undo grace', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    deleteMemory.mockReset()
    deleteMemory.mockResolvedValue(undefined)
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('a single tap never deletes — DELETE fires only after the grace period', async () => {
    renderMessage()
    openBlock()
    fireEvent.click(screen.getByLabelText('Forget memory: Jacob drives a 2010 Civic'))

    expect(deleteMemory).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(FORGET_GRACE_MS - 1)
    })
    expect(deleteMemory).not.toHaveBeenCalled()

    await act(async () => {
      vi.advanceTimersByTime(1)
    })
    expect(deleteMemory).toHaveBeenCalledExactlyOnceWith('mem-1')

    vi.useRealTimers()
    await waitFor(() => expect(screen.getByText(/forgotten/)).toBeInTheDocument())
  })

  it('undo within the grace period cancels — no DELETE, memory intact', () => {
    renderMessage()
    openBlock()
    fireEvent.click(screen.getByLabelText('Forget memory: Jacob drives a 2010 Civic'))
    fireEvent.click(screen.getByLabelText('Undo forgetting: Jacob drives a 2010 Civic'))

    act(() => {
      vi.advanceTimersByTime(FORGET_GRACE_MS * 2)
    })

    expect(deleteMemory).not.toHaveBeenCalled()
    // Back to resting state: forget is offered again, nothing struck through.
    expect(screen.getByLabelText('Forget memory: Jacob drives a 2010 Civic')).toBeInTheDocument()
    expect(screen.queryByText(/forgotten/)).not.toBeInTheDocument()
  })

  it('items without a memoryId get no forget affordance', () => {
    renderMessage()
    openBlock()
    expect(screen.getByText('a knowledge chunk with no id')).toBeInTheDocument()
    expect(
      screen.queryByLabelText('Forget memory: a knowledge chunk with no id'),
    ).not.toBeInTheDocument()
  })

  it('a failed DELETE surfaces the error instead of pretending', async () => {
    deleteMemory.mockRejectedValue(new Error('HTTP 404'))
    renderMessage()
    openBlock()
    fireEvent.click(screen.getByLabelText('Forget memory: Jacob drives a 2010 Civic'))

    await act(async () => {
      vi.advanceTimersByTime(FORGET_GRACE_MS)
    })

    vi.useRealTimers()
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert').textContent).toContain('not forgotten')
  })
})
