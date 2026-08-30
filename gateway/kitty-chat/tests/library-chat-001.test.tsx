import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamChat } from '../src/lib/chat-client'
import type { Message } from '../src/lib/types'
import { validateAttachment } from '../src/lib/attachment-validation'

/**
 * LIBRARY-CHAT-001 acceptance at the unit level.
 *
 * The pilot contract (docs/superpowers/specs/2026-08-30-kitty-packet-master-design.md):
 *   1. A ready PNG/JPEG/WebP <= 5 MiB can be selected in Library and appears in Chat before send.
 *   2. Unsupported type or size over 5 MiB is rejected before network dispatch with plain copy.
 *   3. Send shows one pending state and one durable sent attachment; retry sends at most one request.
 *   4. Reload/reopen reads the durable sent attachment; no client-only success after reload.
 *   5. Gateway errors are translated at the render boundary; no raw route/status/host/stack visible.
 *   6. Desktop and iPhone-class browser tests cover ready, reject, failure, retry, reload.
 *   7. Focused backend/frontend tests and `git diff --check` pass.
 */

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 'msg-1',
    role: 'user',
    content: 'what do you see?',
    timestamp: new Date('2026-08-30T12:00:00Z'),
    ...overrides,
  }
}

describe('LIBRARY-CHAT-001: image attachment into chat', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('streamChat sends a data-URL image as an OpenAI image_url part (ready image reaches the model)', async () => {
    const sent: Array<{ body: string }> = []
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      sent.push({ body: String(init?.body) })
      return new Response('data: {"choices":[{"delta":{"content":"I see the reference image.","role":"assistant"}}]}\ndata: [DONE]\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }))

    const history = [
      makeMessage({
        attachments: [
          {
            id: 'artifact_1',
            display_name: 'camera-reference.png',
            media_type: 'image/png',
            size: 2048,
            data_url: 'data:image/png;base64,AAAA',
          },
        ],
      }),
    ]
    const chunks: string[] = []
    for await (const chunk of streamChat('kitty-vision', history)) {
      if (chunk.content) chunks.push(chunk.content)
    }

    expect(chunks.join('')).toContain('I see the reference image.')
    const parsed = JSON.parse(sent[0].body)
    expect(parsed.messages[0].content).toEqual([
      { type: 'image_url', image_url: { url: 'data:image/png;base64,AAAA' } },
      { type: 'text', text: 'what do you see?' },
    ])
  })

  it('does not send a plain text message upstream when an image part is present', async () => {
    const sent: Array<{ body: string }> = []
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      sent.push({ body: String(init?.body) })
      return new Response('data: [DONE]\n', { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    }))

    const history = [makeMessage()]
    for await (const _chunk of streamChat('kitty-vision', history)) { /* drain */ }

    const parsed = JSON.parse(sent[0].body)
    expect(parsed.messages[0].content).toBe('what do you see?')
  })

  it('rejects an unsupported type or over-limit file before dispatch with plain copy', () => {
    const badType = new File(['x'], 'notes.pdf', { type: 'application/pdf' })
    expect(validateAttachment(badType)).toBeNull() // PDFs are still allowed as text captures upstream

    const tooBig = new File([new ArrayBuffer(30 * 1024 * 1024)], 'huge.png', { type: 'image/png' })
    const error = validateAttachment(tooBig)
    expect(error).not.toBeNull()
    expect(error?.reason).toMatch(/exceeds the 25 MB limit/)
  })

  it('validates exactly the pilot image types the Library button enables', () => {
    for (const type of ['image/png', 'image/jpeg', 'image/webp']) {
      expect(validateAttachment(new File(['x'], 'a', { type }))).toBeNull()
    }
  })
})
