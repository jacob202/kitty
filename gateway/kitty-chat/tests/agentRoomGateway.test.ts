import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  fetchGlobalAgentInbox,
  fetchGlobalAgentMessages,
  fetchGlobalAgentRoom,
  postGlobalAgentMessage,
  updateGlobalAgentReceipt,
} from '../src/lib/gateway'

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('global agent room gateway client', () => {
  it('loads the canonical global room and recent messages', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: 'workspace_global', agents: [], messages: [] }))
      .mockResolvedValueOnce(jsonResponse({ messages: [{ id: 'message_1' }] }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchGlobalAgentRoom()
    await fetchGlobalAgentMessages(42)

    expect(fetchMock.mock.calls[0][0]).toBe('/proxy/agent-room/global')
    expect(fetchMock.mock.calls[1][0]).toBe('/proxy/agent-room/global/messages?limit=42')
  })

  it('reads Jacob inbox without silently changing receipts', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ messages: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchGlobalAgentInbox(true, 25)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/proxy/agent-room/global/inbox/jacob?unread_only=true&limit=25')
    expect((init as RequestInit).method).toBeUndefined()
  })

  it('posts direct and broadcast messages only as Jacob', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ id: 'message_1' }))
    vi.stubGlobal('fetch', fetchMock)

    await postGlobalAgentMessage({
      recipientId: 'claude',
      content: 'Review this.',
      messageKind: 'prompt',
    })
    await postGlobalAgentMessage({
      recipientId: null,
      content: 'Status for everyone.',
      messageKind: 'status',
    })

    const firstBody = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))
    const secondBody = JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))
    expect(firstBody).toEqual({
      sender_id: 'jacob', recipient_id: 'claude', content: 'Review this.',
      message_kind: 'prompt', parent_message_id: null,
    })
    expect(secondBody.recipient_id).toBeNull()
    expect(secondBody.sender_id).toBe('jacob')
  })

  it('preserves reply parent ids when posting into a thread', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 'message_reply' }))
    vi.stubGlobal('fetch', fetchMock)

    await postGlobalAgentMessage({
      recipientId: 'codex',
      content: 'Following up.',
      messageKind: 'prompt',
      parentMessageId: 'message_root',
    })

    const body = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))
    expect(body.parent_message_id).toBe('message_root')
  })

  it('acknowledges only as Jacob', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ receipt_state: 'acknowledged' }))
    vi.stubGlobal('fetch', fetchMock)

    await updateGlobalAgentReceipt('message_1', 'acknowledged')

    expect(fetchMock.mock.calls[0][0]).toBe('/proxy/agent-room/global/messages/message_1/receipts')
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      participant_id: 'jacob', state: 'acknowledged',
    })
  })
})
