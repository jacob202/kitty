import { Message } from './types'

// All OWUI calls go through the Next.js proxy route — avoids CORS and keeps key server-side
const OPENWEBUI_BASE = '/proxy'
const OPENWEBUI_KEY  = ''  // key is injected server-side by the proxy

export interface StreamChunk {
  content: string
  done: boolean
}

export async function* streamChat(
  model: string,
  messages: Message[],
  signal?: AbortSignal
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${OPENWEBUI_BASE}/api/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(OPENWEBUI_KEY ? { Authorization: `Bearer ${OPENWEBUI_KEY}` } : {}),
    },
    body: JSON.stringify({
      model,
      stream: true,
      messages: messages.map(m => ({ role: m.role, content: m.content })),
    }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`OpenWebUI error ${response.status}: ${await response.text()}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  if (!reader) return

  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') { yield { content: '', done: true }; return }
      try {
        const json = JSON.parse(data)
        const content = json.choices?.[0]?.delta?.content ?? ''
        if (content) yield { content, done: false }
      } catch { /* skip malformed */ }
    }
  }
  yield { content: '', done: true }
}

export async function fetchModels(): Promise<string[]> {
  try {
    const res = await fetch(`${OPENWEBUI_BASE}/api/models`, {
      headers: OPENWEBUI_KEY ? { Authorization: `Bearer ${OPENWEBUI_KEY}` } : {},
    })
    if (!res.ok) return []
    const json = await res.json()
    return (json.data ?? []).map((m: { id: string }) => m.id)
  } catch {
    return []
  }
}
