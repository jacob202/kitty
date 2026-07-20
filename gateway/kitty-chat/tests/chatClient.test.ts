import { describe, expect, it, afterEach, vi } from 'vitest'
import { streamChat, type StreamChunk } from '../src/lib/chat-client'
import type { Message } from '../src/lib/types'

function sseResponse(events: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) controller.enqueue(encoder.encode(event))
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

async function collect(events: string[]): Promise<StreamChunk[]> {
  vi.stubGlobal('fetch', vi.fn(async () => sseResponse(events)))
  const messages: Message[] = [
    { id: 'm1', role: 'user', content: 'hi', timestamp: new Date() },
  ]
  const chunks: StreamChunk[] = []
  for await (const chunk of streamChat('kitty-default', messages)) {
    chunks.push(chunk)
  }
  return chunks
}

describe('streamChat memory trailer (CR-05)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses structured memory evidence without disturbing content chunks', async () => {
    const chunks = await collect([
      'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
      'data: {"memory_items": [{"text":"decided on FastAPI","memory_id":"mem-fastapi"},{"text":"prefers dark mode"}]}\n\n',
      'data: [DONE]\n\n',
    ])
    expect(chunks).toEqual([
      { content: 'Hel', done: false },
      { content: 'lo', done: false },
      {
        content: '',
        done: false,
        memoryItems: [
          { text: 'decided on FastAPI', memoryId: 'mem-fastapi' },
          { text: 'prefers dark mode' },
        ],
      },
      { content: '', done: true },
    ])
  })

  it('yields no memoryItems when the stream has no trailer', async () => {
    const chunks = await collect([
      'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
      'data: [DONE]\n\n',
    ])
    expect(chunks).toEqual([
      { content: 'Hello', done: false },
      { content: '', done: true },
    ])
    expect(chunks.some((c) => c.memoryItems)).toBe(false)
  })

  it('drops non-string entries and ignores an empty or malformed trailer', async () => {
    const chunks = await collect([
      'data: {"memory_items": ["kept", 42, null, "also kept"]}\n\n',
      'data: {"memory_items": "not-an-array"}\n\n',
      'data: {"memory_items": []}\n\n',
      'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n',
      'data: [DONE]\n\n',
    ])
    expect(chunks).toEqual([
      {
        content: '',
        done: false,
        memoryItems: [{ text: 'kept' }, { text: 'also kept' }],
      },
      { content: 'Hi', done: false },
      { content: '', done: true },
    ])
  })
})
