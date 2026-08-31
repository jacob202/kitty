import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ChatMessage } from '../src/components/ChatMessage'
import type { Message } from '../src/lib/types'

describe('ChatMessage typed objects', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders a kitty-action reference as the authoritative live action card', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input).includes('/proxy/actions/42')) {
        return new Response(JSON.stringify({
          id: 42,
          created_at: 1,
          source_kind: 'chat',
          source_id: 'message-7',
          kind: 'calendar.event.create',
          title: 'Schedule dentist',
          preview: 'Create a dentist appointment.',
          payload: { title: 'Dentist' },
          risk_tier: 'T2',
          status: 'proposed',
          result: null,
          decided_at: null,
          executed_at: null,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('not found', { status: 404 })
    })
    const message: Message = {
      id: 'm-action',
      role: 'assistant',
      content: 'I prepared this action.\n\n```kitty-action\n{"action_id":42}\n```',
      timestamp: new Date(),
    }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

    render(
      <QueryClientProvider client={client}>
        <ChatMessage message={message} chatId="chat-1" messageIndex={0} />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Schedule dentist')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve action' })).toBeInTheDocument()
    expect(screen.queryByText('{"action_id":42}')).not.toBeInTheDocument()
  })

  it('renders a kitty-artifact reference as an openable durable object', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input).includes('/proxy/artifacts/artifact_1')) {
        return new Response(JSON.stringify({
          id: 'artifact_1',
          project_id: 7,
          kind: 'document',
          media_type: 'text/markdown',
          display_name: 'research-report.md',
          state: 'ready',
          size_bytes: 2048,
          created_at: 1787259000,
          created_by: 'research',
          metadata: {},
          error: null,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('not found', { status: 404 })
    })
    const message: Message = {
      id: 'm-artifact',
      role: 'assistant',
      content: 'Your report is ready.\n\n```kitty-artifact\n{"artifact_id":"artifact_1"}\n```',
      timestamp: new Date(),
    }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

    render(
      <QueryClientProvider client={client}>
        <ChatMessage message={message} chatId="chat-1" messageIndex={1} compact />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('research-report.md')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open artifact' })).toBeInTheDocument()
    expect(screen.queryByText('{"artifact_id":"artifact_1"}')).not.toBeInTheDocument()
  })

})
