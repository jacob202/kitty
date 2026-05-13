'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { Chat, Message, Model, MODELS, COLOR_CYCLE, ChatColor } from '@/lib/types'
import { streamChat } from '@/lib/openwebui'
import { inferMood } from '@/lib/mood'
import { TopBar } from '@/components/TopBar'
import { ChatMessage } from '@/components/ChatMessage'
import { InputBar } from '@/components/InputBar'
import { BriefPanel } from '@/components/BriefPanel'

let chatCounter = 0
function newChatId() { return `chat-${++chatCounter}-${Date.now()}` }
function newMsgId()  { return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}` }

function makeChat(color: ChatColor): Chat {
  return {
    id: newChatId(),
    title: 'new chat',
    messages: [],
    model: MODELS[0].id,
    color,
    createdAt: new Date(),
    updatedAt: new Date(),
  }
}

function getInitials(email?: string): string {
  if (!email) return 'JB'
  const parts = email.replace(/@.*/, '').split(/[._-]/)
  return parts.slice(0, 2).map(p => p[0]?.toUpperCase() ?? '').join('') || 'ME'
}

const USER_INITIALS = getInitials('jacobbrizinski@gmail.com')

export default function KittyChat() {
  const [chats, setChats] = useState<Chat[]>(() => [makeChat('teal')])
  const [activeChatId, setActiveChatId] = useState<string | null>(() => null)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeModel, setActiveModel] = useState<Model>(MODELS[0])
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [tokenCount, setTokenCount] = useState(0)

  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const colorIndexRef = useRef(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const activeChat = chats.find(c => c.id === activeChatId) ?? chats[0] ?? null

  useEffect(() => {
    if (chats.length > 0 && !activeChatId) {
      setActiveChatId(chats[0].id)
    }
  }, [chats, activeChatId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeChat?.messages.length, isStreaming])

  // rough token estimate: ~4 chars per token
  useEffect(() => {
    if (!activeChat) return
    const chars = activeChat.messages.reduce((sum, m) => sum + m.content.length, 0)
    setTokenCount(Math.round(chars / 4))
  }, [activeChat?.messages])

  const handleNewChat = useCallback(() => {
    const color = COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length]
    colorIndexRef.current++
    const chat = makeChat(color)
    chat.model = activeModel.id
    setChats(prev => [...prev, chat])
    setActiveChatId(chat.id)
    setInput('')
  }, [activeModel.id])

  const handleCloseChat = useCallback((id: string) => {
    setChats(prev => {
      const next = prev.filter(c => c.id !== id)
      if (next.length === 0) {
        const fresh = makeChat(COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length])
        colorIndexRef.current++
        return [fresh]
      }
      return next
    })
    setActiveChatId(prev => {
      if (prev !== id) return prev
      const remaining = chats.filter(c => c.id !== id)
      return remaining[remaining.length - 1]?.id ?? null
    })
  }, [chats])

  const handleSelectModel = useCallback((m: Model) => {
    setActiveModel(m)
    if (activeChat) {
      setChats(prev => prev.map(c => c.id === activeChat.id ? { ...c, model: m.id } : c))
    }
  }, [activeChat])

  const updateChat = useCallback((id: string, updater: (c: Chat) => Chat) => {
    setChats(prev => prev.map(c => c.id === id ? updater(c) : c))
  }, [])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isStreaming || !activeChat) return

    const userMsg: Message = {
      id: newMsgId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }

    // derive title from first message
    const isFirst = activeChat.messages.length === 0
    const title = isFirst ? text.slice(0, 32) + (text.length > 32 ? '…' : '') : activeChat.title

    updateChat(activeChat.id, c => ({
      ...c,
      title,
      messages: [...c.messages, userMsg],
      updatedAt: new Date(),
    }))
    setInput('')
    setIsStreaming(true)

    const aiMsgId = newMsgId()
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      model: activeModel.name,
    }

    updateChat(activeChat.id, c => ({ ...c, messages: [...c.messages, aiMsg] }))

    const abort = new AbortController()
    abortRef.current = abort

    try {
      const history = [...activeChat.messages, userMsg]
      let accumulated = ''

      for await (const chunk of streamChat(activeModel.id, history, abort.signal)) {
        if (chunk.done) break
        accumulated += chunk.content
        const content = accumulated
        updateChat(activeChat.id, c => ({
          ...c,
          messages: c.messages.map(m =>
            m.id === aiMsgId ? { ...m, content } : m
          ),
        }))
      }

      const mood = inferMood(accumulated, 'assistant')
      updateChat(activeChat.id, c => ({
        ...c,
        updatedAt: new Date(),
        messages: c.messages.map(m =>
          m.id === aiMsgId ? { ...m, content: accumulated, mood } : m
        ),
      }))
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        updateChat(activeChat.id, c => ({
          ...c,
          messages: c.messages.map(m =>
            m.id === aiMsgId
              ? { ...m, content: `⚠ Error: ${err.message}`, mood: 'confused' as const }
              : m
          ),
        }))
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [input, isStreaming, activeChat, activeModel, updateChat])

  const handlePrompt = useCallback((text: string) => {
    setInput(text)
    setTimeout(() => {
      textareaRef.current?.focus()
      const ta = textareaRef.current
      if (ta) ta.selectionStart = ta.selectionEnd = ta.value.length
    }, 0)
  }, [])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100vh',
      background: 'var(--bg)', overflow: 'hidden',
    }}
      onClick={() => showModelMenu && setShowModelMenu(false)}
    >
      <TopBar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={handleNewChat}
        onCloseChat={handleCloseChat}
        activeModel={activeModel}
        onSelectModel={handleSelectModel}
        showModelMenu={showModelMenu}
        setShowModelMenu={setShowModelMenu}
      />

      {/* Message area */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {!activeChat || activeChat.messages.length === 0 ? (
          <BriefPanel
            chats={chats}
            onSelectChat={id => { setActiveChatId(id) }}
            onPrompt={handlePrompt}
          />
        ) : (
          <div>
            {activeChat.messages.map((msg, i) => {
              const isLast = i === activeChat.messages.length - 1
              return (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  isStreaming={isStreaming && isLast && msg.role === 'assistant'}
                  initials={USER_INITIALS}
                />
              )
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <InputBar
        value={input}
        onChange={setInput}
        onSend={handleSend}
        disabled={isStreaming}
        chatTitle={activeChat?.title}
        modelName={activeModel.name}
        modelColor={activeModel.color}
        tokenCount={tokenCount}
        maxTokens={200000}
        textareaRef={textareaRef}
      />
    </div>
  )
}

