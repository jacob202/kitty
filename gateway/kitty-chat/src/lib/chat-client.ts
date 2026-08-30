import { Message, normalizeMemoryEvidence, type MemoryEvidence, type MessageAttachment, type ToolCall } from './types';

// All gateway calls go through the Next.js proxy route — avoids CORS and keeps key server-side
const GATEWAY_BASE = '/proxy';

export interface StreamChunk {
  content: string;
  done: boolean;
  /** Present on the single trailer event listing memories that informed the reply. */
  memoryItems?: MemoryEvidence[];
  /** Accumulated tool calls snapshot — present on every delta that touches tool_calls. */
  toolCalls?: ToolCall[];
  provider?: string;
  requestedModel?: string;
  toolsState?: 'available' | 'unavailable';
}

/** Machine-readable chat-turn failure kinds. Mirrors gateway/chat_errors.py. */
export type ChatErrorKind = 'routing' | 'upstream' | 'network' | 'cut-off';

/** User-facing copy per failure kind, written for a phone screen. */
const FRIENDLY_CHAT_MESSAGES: Record<ChatErrorKind, string> = {
  routing:
    "Kitty couldn't complete this request — the selected model provider didn't accept it (it may be out of credit or unavailable). Your message is saved. Tap retry, or check Settings to pick a different model.",
  upstream:
    "Kitty's model provider couldn't finish this request. Your message is saved — tap retry to try again.",
  network:
    "Kitty couldn't reach its gateway. Check that Kitty is running, then tap retry — your message is saved.",
  'cut-off': "Kitty's reply was cut off before it finished. Tap retry to continue.",
};

export type ChatFriendlyError = { kind: ChatErrorKind; userMessage: string };

/** A chat failure carrying user-facing copy; raw detail stays off-screen. */
export class ChatSendError extends Error {
  kind: ChatErrorKind;
  userMessage: string;

  constructor(kind: ChatErrorKind, userMessage: string, detail?: string) {
    super(userMessage);
    this.name = 'ChatSendError';
    this.kind = kind;
    this.userMessage = userMessage;
    if (detail) (this as { detail?: string }).detail = detail;
  }
}

/** Map any thrown value to friendly, jargon-free recovery copy. */
export function friendlyChatError(err: unknown): ChatFriendlyError {
  if (err instanceof ChatSendError) {
    return { kind: err.kind, userMessage: err.userMessage };
  }
  // A fetch() failure (proxy/gateway unreachable) surfaces as TypeError.
  if (err instanceof TypeError) {
    return { kind: 'network', userMessage: FRIENDLY_CHAT_MESSAGES.network };
  }
  if (err instanceof Error && err.name === 'AbortError') {
    return { kind: 'cut-off', userMessage: FRIENDLY_CHAT_MESSAGES['cut-off'] };
  }
  return { kind: 'cut-off', userMessage: FRIENDLY_CHAT_MESSAGES['cut-off'] };
}

async function notOkError(response: Response): Promise<ChatSendError> {
  let raw = '';
  try {
    raw = await response.text();
  } catch {
    raw = '';
  }
  let detail = raw.slice(0, 300);
  try {
    const parsed = JSON.parse(raw);
    const inner = parsed?.error && typeof parsed.error === 'object' ? parsed.error : parsed;
    detail = String(inner?.message ?? inner?.detail ?? raw).slice(0, 300);
  } catch {
    // not JSON — keep raw status text
  }
  const status = response.status;
  // Server/upstream trouble is retryable as-is; 4xx usually needs a model/provider change.
  const kind: ChatErrorKind = status >= 500 ? 'upstream' : 'routing';
  return new ChatSendError(kind, FRIENDLY_CHAT_MESSAGES[kind], detail || `HTTP ${status}`);
}

interface ToolCallAccumulator {
  id: string;
  name: string;
  arguments: string;
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
      messages: messages.map((m) => {
        const parts: Array<{ type: string; text?: string; image_url?: { url: string } }> = []
        const stagedImages = (m.attachments ?? []).filter((a): a is MessageAttachment & { data_url: string } => Boolean(a.data_url))
        if (stagedImages.length > 0) {
          for (const image of stagedImages) {
            parts.push({ type: 'image_url', image_url: { url: image.data_url } })
          }
        }
        if (m.content) {
          parts.push({ type: 'text', text: m.content })
        }
        return {
          role: m.role,
          content: parts.length > 0 && parts.some((part) => part.type === 'image_url') ? parts : m.content,
        }
      }),
    }),
    signal,
  });

  if (!response.ok) {
    throw await notOkError(response);
  }

  const provider = response.headers.get('X-Kitty-Provider-Selected') ?? undefined;
  const requestedModel = response.headers.get('X-Kitty-Model-Requested') ?? undefined;
  const rawToolsState = response.headers.get('X-Kitty-Tools-State');
  const toolsState = rawToolsState === 'available' || rawToolsState === 'unavailable'
    ? rawToolsState
    : undefined;
  if (provider || requestedModel || toolsState) {
    yield { content: '', done: false, provider, requestedModel, toolsState };
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  if (!reader) return;

  let buffer = '';
  const toolAccum: ToolCallAccumulator[] = [];
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
        // User-facing error event emitted by the gateway before the stream
        // tears down (gateway/chat_errors.py). Round-trips plain-language copy.
        if (json?.error && typeof json.error === 'object') {
          const kind =
            (json.error.kind as ChatErrorKind) &&
            json.error.kind in FRIENDLY_CHAT_MESSAGES
              ? (json.error.kind as ChatErrorKind)
              : 'upstream';
          const message =
            typeof json.error.message === 'string' && json.error.message.trim()
              ? json.error.message
              : FRIENDLY_CHAT_MESSAGES[kind];
          throw new ChatSendError(kind, message);
        }
        if (Array.isArray(json.memory_items)) {
          const memoryItems = normalizeMemoryEvidence(json.memory_items);
          if (memoryItems.length) yield { content: '', done: false, memoryItems };
          continue;
        }
        const delta = json.choices?.[0]?.delta;
        if (!delta) continue;

        const tcDeltas = delta.tool_calls as
          | Array<{ index: number; id?: string; function?: { name?: string; arguments?: string } }>
          | undefined;
        if (tcDeltas) {
          for (const tc of tcDeltas) {
            const idx = tc.index;
            if (!toolAccum[idx]) {
              toolAccum[idx] = { id: tc.id ?? '', name: '', arguments: '' };
            }
            if (tc.id) toolAccum[idx].id = tc.id;
            if (tc.function?.name) toolAccum[idx].name = tc.function.name;
            if (tc.function?.arguments) toolAccum[idx].arguments += tc.function.arguments;
          }
          yield { content: '', done: false, toolCalls: toolAccum.map((t) => ({ ...t })) };
          continue;
        }

        const content = delta.content ?? '';
        if (content) yield { content, done: false };
      } catch (err) {
        // A typed ChatSendError thrown above must propagate, not be swallowed
        // by the malformed-line guard.
        if (err instanceof ChatSendError) throw err;
        /* skip malformed */
      }
    }
  }
  // ponytail: reader closed without [DONE] — stream was cut, not completed.
  // No user-facing raw-jargon message; use the friendly cut-off copy.
  throw new ChatSendError('cut-off', FRIENDLY_CHAT_MESSAGES['cut-off']);
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
