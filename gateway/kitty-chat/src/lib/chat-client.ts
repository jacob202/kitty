import { Message, normalizeMemoryEvidence, type MemoryEvidence } from './types';

// All gateway calls go through the Next.js proxy route — avoids CORS and keeps key server-side
const GATEWAY_BASE = '/proxy';

export interface StreamChunk {
  content: string;
  done: boolean;
  /** Present on the single trailer event listing memories that informed the reply. */
  memoryItems?: MemoryEvidence[];
}

export async function* streamChat(
  model: string,
  messages: Message[],
  signal?: AbortSignal,
  projectId?: number,
  conversationId?: string,
  userMessageId?: string,
  conversationTitle?: string,
  attachmentIds?: string[],
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${GATEWAY_BASE}/api/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      stream: true,
      ...(projectId === undefined ? {} : { project_id: projectId }),
      ...(conversationId === undefined ? {} : { conversation_id: conversationId }),
      ...(userMessageId === undefined ? {} : { user_message_id: userMessageId }),
      ...(conversationTitle === undefined ? {} : { conversation_title: conversationTitle }),
      ...(attachmentIds === undefined ? {} : { attachment_ids: attachmentIds }),
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Gateway error ${response.status}: ${await response.text()}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  if (!reader) return;

  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') {
        yield { content: '', done: true };
        return;
      }
      try {
        const json = JSON.parse(data);
        // CR-04 memory trailer: one non-content event before [DONE].
        if (Array.isArray(json.memory_items)) {
          const memoryItems = normalizeMemoryEvidence(json.memory_items);
          if (memoryItems.length) yield { content: '', done: false, memoryItems };
          continue;
        }
        const content = json.choices?.[0]?.delta?.content ?? '';
        if (content) yield { content, done: false };
      } catch {
        /* skip malformed */
      }
    }
  }
  // ponytail: reader closed without [DONE] — stream was cut, not completed
  throw new Error('Stream closed without [DONE] — incomplete response');
}

export async function fetchModels(): Promise<string[]> {
  try {
    const res = await fetch(`${GATEWAY_BASE}/api/models`);
    if (!res.ok) return [];
    const json = await res.json();
    return (json.data ?? []).map((m: { id: string }) => m.id);
  } catch {
    return [];
  }
}
