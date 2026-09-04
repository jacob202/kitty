import { describe, expect, it, afterEach, vi } from 'vitest'
import {
  streamChat,
  ChatSendError,
  friendlyChatError,
  type StreamChunk,
} from '../src/lib/chat-client'
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

describe('streamChat truthful failure recovery', () => {
  afterEach(() => vi.unstubAllGlobals())

  async function rejected(events: string[]): Promise<unknown> {
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(events)))
    const messages: Message[] = [
      { id: 'm1', role: 'user', content: 'hi', timestamp: new Date() },
    ]
    const out: unknown[] = []
    try {
      for await (const chunk of streamChat('kitty-default', messages)) out.push(chunk)
    } catch (err) {
      return err
    }
    return out
  }

  it('maps a cut stream (no [DONE]) to friendly cut-off copy, never raw jargon', async () => {
    const err = await rejected(['data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'])
    expect(err).toBeInstanceOf(ChatSendError)
    const sendError = err as ChatSendError
    expect(sendError.kind).toBe('cut-off')
    expect(sendError.userMessage).toContain('cut off')
    // Regression: the old raw programmer string must never reach the user.
    expect(sendError.userMessage).not.toContain('Stream closed without [DONE]')
  })

  it('round-trips a gateway SSE error event with its plain-language message', async () => {
    const err = await rejected([
      'data: {"error":{"kind":"routing","message":"kitty could not reach the model provider"}}\n\n',
    ])
    expect(err).toBeInstanceOf(ChatSendError)
    const sendError = err as ChatSendError
    expect(sendError.kind).toBe('routing')
    expect(sendError.userMessage).toBe('kitty could not reach the model provider')
  })

  it('throws friendly routing copy when the gateway rejects with 4xx JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { message: 'provider out of credit' } }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    )
    const messages: Message[] = [{ id: 'm1', role: 'user', content: 'hi', timestamp: new Date() }]
    await expect(
      (async () => {
        const out: StreamChunk[] = []
        for await (const chunk of streamChat('kitty-default', messages)) out.push(chunk)
        return out
      })()
    ).rejects.toMatchObject({ kind: 'routing', userMessage: expect.stringContaining('no model provider') })
  })

  it('maps a structured attachment 4xx to restage copy', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({
          detail: {
            kind: 'attachment',
            message: 'Kitty could not use that image. Remove it and stage the image again.',
          },
        }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    )
    const messages: Message[] = [{
      id: 'm1',
      role: 'user',
      content: 'what do you see?',
      timestamp: new Date(),
      attachments: [{
        id: 'artifact_1',
        display_name: 'camera-reference.png',
        media_type: 'image/png',
        size: 2048,
      }],
    }]
    await expect(
      (async () => {
        const out: StreamChunk[] = []
        for await (const chunk of streamChat('kitty-auto', messages, undefined, undefined, undefined, undefined, undefined, ['artifact_1'])) out.push(chunk)
        return out
      })()
    ).rejects.toMatchObject({
      kind: 'attachment',
      userMessage: expect.stringMatching(/remove|restage/i),
    })
  })

  it('throws friendly upstream copy on 5xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: 'gateway exploded' }), {
          status: 502,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    )
    const messages: Message[] = [{ id: 'm1', role: 'user', content: 'hi', timestamp: new Date() }]
    await expect(
      (async () => {
        const out: StreamChunk[] = []
        for await (const chunk of streamChat('kitty-default', messages)) out.push(chunk)
        return out
      })()
    ).rejects.toMatchObject({ kind: 'upstream', userMessage: expect.stringContaining('provider') })
  })

  it('maps a fetch network failure to network copy', () => {
    const mapped = friendlyChatError(new TypeError('Failed to fetch'))
    expect(mapped.kind).toBe('network')
    expect(mapped.userMessage).toContain('gateway')
    expect(mapped.userMessage).not.toContain('Failed to fetch')
  })
})
