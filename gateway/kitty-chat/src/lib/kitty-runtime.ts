'use client'

import { useMemo, useRef, useCallback } from 'react'
import {
  useExternalStoreRuntime,
  type ExternalStoreAdapter,
} from '@assistant-ui/react'
import type { ThreadMessageLike } from '@assistant-ui/react'
import type { Message, Model } from './types'

function toThreadMessage(msg: Message): ThreadMessageLike {
  const parts: Array<
    | { type: 'text'; text: string }
    | { type: 'tool-call'; toolCallId: string; toolName: string; argsText: string }
  > = []
  if (msg.content) {
    parts.push({ type: 'text', text: msg.content })
  }
  if (msg.toolCalls?.length) {
    for (const tc of msg.toolCalls) {
      parts.push({ type: 'tool-call', toolCallId: tc.id, toolName: tc.name, argsText: tc.arguments })
    }
  }
  return {
    id: msg.id,
    role: msg.role === 'user' ? 'user' : 'assistant',
    content: parts,
    createdAt: msg.timestamp,
    ...(msg.model ? { metadata: { custom: { model: msg.model } } } : {}),
  }
}

export interface KittyRuntimeOptions {
  messages: Message[]
  isStreaming: boolean
  activeModel: Model
  onSend: (text: string) => void
  onCancel: () => void
  onReload?: () => void
}

export function useKittyRuntime(options: KittyRuntimeOptions) {
  const { messages, isStreaming, onSend, onCancel, onReload } = options
  const onSendRef = useRef(onSend)
  const onCancelRef = useRef(onCancel)
  const onReloadRef = useRef(onReload)
  onSendRef.current = onSend
  onCancelRef.current = onCancel
  onReloadRef.current = onReload

  const handleNew = useCallback(async (msg: { content: readonly { type: string; text?: string }[] }) => {
    const parts = Array.isArray(msg.content) ? msg.content : []
    const text = parts
      .filter((p): p is { type: 'text'; text: string } => p.type === 'text' && typeof p.text === 'string')
      .map((p) => p.text)
      .join('\n')
    if (text.trim()) onSendRef.current(text)
  }, [])

  const handleCancel = useCallback(async () => {
    onCancelRef.current()
  }, [])

  const handleReload = useCallback(async () => {
    onReloadRef.current?.()
  }, [])

  const adapter: ExternalStoreAdapter<Message> = useMemo(
    () => ({
      isRunning: isStreaming,
      messages,
      convertMessage: toThreadMessage,
      onNew: handleNew,
      onCancel: handleCancel,
      onReload: handleReload,
    }),
    [isStreaming, messages, handleNew, handleCancel, handleReload],
  )

  return useExternalStoreRuntime(adapter)
}
