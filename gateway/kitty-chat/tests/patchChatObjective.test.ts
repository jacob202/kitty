import { describe, expect, it, afterEach, vi } from 'vitest'
import { patchChatObjective } from '../src/lib/gateway'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    statusText: status === 200 ? 'OK' : 'Not Found',
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('patchChatObjective', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('PATCHes the CR-01 objective endpoint and returns the server value', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ id: 'chat-1', title: 'First Chat', objective: 'ship the resume' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await patchChatObjective('chat-1', 'ship the resume')

    expect(result).toEqual({ objective: 'ship the resume' })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/proxy/chats/chat-1/objective')
    expect(init.method).toBe('PATCH')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body as string)).toEqual({ objective: 'ship the resume' })
  })

  it('normalizes a cleared objective (key omitted by the gateway) to null', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ id: 'chat-1', title: 'First Chat' })))

    const result = await patchChatObjective('chat-1', null)

    expect(result).toEqual({ objective: null })
  })

  it('URL-encodes the chat id', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: 'a/b' }))
    vi.stubGlobal('fetch', fetchMock)

    await patchChatObjective('a/b', 'goal')

    expect(fetchMock.mock.calls[0][0]).toBe('/proxy/chats/a%2Fb/objective')
  })

  it('throws with the status on a gateway error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'missing' }, 404)))

    await expect(patchChatObjective('ghost', 'goal')).rejects.toThrow('404')
  })
})
