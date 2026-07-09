import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'

import { ChatMessage } from '../src/components/ChatMessage'
import type { Message } from '../src/lib/types'

const kittyMsg: Message = {
  id: 'm1',
  role: 'assistant',
  content: 'hi. i checked the thing.',
  timestamp: new Date(),
}

describe('ChatMessage actions', () => {
  afterEach(cleanup)

  it('shows copy and retry for a finished kitty message with onRetry', () => {
    const onRetry = vi.fn()
    render(<ChatMessage message={kittyMsg} onRetry={onRetry} />)
    expect(screen.getByTitle('copy message')).toBeInTheDocument()
    fireEvent.click(screen.getByTitle('regenerate this reply'))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('hides retry when onRetry is not provided', () => {
    render(<ChatMessage message={kittyMsg} />)
    expect(screen.queryByTitle('regenerate this reply')).not.toBeInTheDocument()
  })

  it('shows no actions while streaming', () => {
    render(<ChatMessage message={{ ...kittyMsg, content: '' }} isStreaming />)
    expect(screen.queryByTitle('copy message')).not.toBeInTheDocument()
  })

  it('shows no actions on user messages', () => {
    render(<ChatMessage message={{ ...kittyMsg, role: 'user' }} onRetry={vi.fn()} />)
    expect(screen.queryByTitle('copy message')).not.toBeInTheDocument()
  })
})
