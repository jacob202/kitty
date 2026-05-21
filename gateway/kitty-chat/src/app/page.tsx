'use client'
import { startTransition, useState, useRef, useEffect, useCallback } from 'react'
import { Chat, Message, Model, MODELS, COLOR_CYCLE, ChatColor } from '@/lib/types'
import { streamChat } from '@/lib/openwebui'
import { inferMood } from '@/lib/mood'
import { TopBar } from '@/components/TopBar'
import { ChatMessage } from '@/components/ChatMessage'
import { InputBar } from '@/components/InputBar'
import { BriefPanel } from '@/components/BriefPanel'
import { Rail } from '@/components/Rail'
import { SessionSidebar } from '@/components/SessionSidebar'
import { RightBar } from '@/components/RightBar'
import { fetchGatewayBrief, fetchGatewayModels, fetchGatewaySearch, fetchGatewayMood, loadGatewayChats, saveGatewayChat, deleteGatewayChat, synthesizeSpeech, type GatewayBrief, type GatewaySearchSnapshot } from '@/lib/gateway'

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

function latestSearchQuery(chat: Chat | null): string {
  if (!chat) return ''
  const lastUser = [...chat.messages].reverse().find(message => message.role === 'user')?.content?.trim()
  if (lastUser) return lastUser
  if (chat.title !== 'new chat') return chat.title.trim()
  return ''
}

export default function KittyChat() {
  const [chats, setChats] = useState<Chat[]>(() => [makeChat('teal')])
  const [activeChatId, setActiveChatId] = useState<string | null>(() => null)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [availableModels, setAvailableModels] = useState<Model[]>(MODELS)
  const [activeModel, setActiveModel] = useState<Model>(MODELS[0])
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [tokenCount, setTokenCount] = useState(0)
  const [brief, setBrief] = useState<GatewayBrief | null>(null)
  const [searchSnapshot, setSearchSnapshot] = useState<GatewaySearchSnapshot | null>(null)
  const [kittyMood, setKittyMood] = useState<import('@/lib/types').KittyMood>('idle')
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null)

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

  useEffect(() => {
    let cancelled = false

    void (async () => {
      // Load persisted chats from gateway first
      const saved = await loadGatewayChats()
      if (!cancelled && saved && saved.length > 0) {
        startTransition(() => {
          setChats(saved)
          setActiveChatId(saved[saved.length - 1].id)
        })
      }

      const models = await fetchGatewayModels()
      if (cancelled) return
      startTransition(() => {
        setAvailableModels(models)
        setActiveModel(current => models.find(model => model.id === current.id) ?? models[0] ?? current)
      })

      const liveBrief = await fetchGatewayBrief()
      if (cancelled) return
      startTransition(() => {
        setBrief(liveBrief)
      })
    })()

    return () => {
      cancelled = true
    }
  }, [])

  // Only re-run when the last user message or active chat actually changes.
  // Avoids firing N times per streaming response.
  const lastUserMsg = activeChat?.messages.findLast(m => m.role === 'user')?.content ?? ''
  const searchKey = `${activeChatId}:${lastUserMsg}`

  useEffect(() => {
    let cancelled = false
    const query = lastUserMsg.trim()

    if (!query) {
      setSearchSnapshot(null)
      return () => { cancelled = true }
    }

    void (async () => {
      const nextSnapshot = await fetchGatewaySearch(query, 3)
      if (cancelled) return
      startTransition(() => setSearchSnapshot(nextSnapshot))
    })()

    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey])

  // rough token estimate: ~4 chars per token
  useEffect(() => {
    if (!activeChat) return
    const chars = activeChat.messages.reduce((sum, m) => sum + m.content.length, 0)
    setTokenCount(Math.round(chars / 4))
  }, [activeChat?.messages])

  // Poll gateway mood every 3s so the avatar reflects backend state
  useEffect(() => {
    let alive = true
    const poll = async () => {
      const state = await fetchGatewayMood()
      if (alive && state) setKittyMood(state.mood)
    }
    void poll()
    const id = setInterval(() => { void poll() }, 3000)
    return () => { alive = false; clearInterval(id) }
  }, [])

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
    void deleteGatewayChat(id)
    setChats(prev => {
      let next = prev.filter(c => c.id !== id)
      if (next.length === 0) {
        const fresh = makeChat(COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length])
        colorIndexRef.current++
        next = [fresh]
      }
      // Update active ID inside the same state batch to avoid stale closure
      setActiveChatId(cur => cur === id ? (next[next.length - 1]?.id ?? null) : cur)
      return next
    })
  }, [])

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

      // TTS playback — speak the response if voice is enabled
      if (voiceEnabled && accumulated) {
        void (async () => {
          try {
            // Strip markdown and keep it under ~500 chars for snappy playback
            const plain = accumulated
              .replace(/```[\s\S]*?```/g, '')
              .replace(/[#*`_~>]/g, '')
              .trim()
              .slice(0, 500)
            ttsAudioRef.current?.pause()
            const url = await synthesizeSpeech(plain)
            const audio = new Audio(url)
            ttsAudioRef.current = audio
            audio.play()
            audio.onended = () => URL.revokeObjectURL(url)
          } catch { /* TTS failure is non-fatal */ }
        })()
      }
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
      // Persist the completed chat
      setChats(current => {
        const saved = current.find(c => c.id === activeChat.id)
        if (saved) void saveGatewayChat(saved)
        return current
      })
    }
  }, [input, isStreaming, activeChat, activeModel, updateChat, voiceEnabled])

  const handlePrompt = useCallback((text: string) => {
    setInput(text)
    setTimeout(() => {
      textareaRef.current?.focus()
      const ta = textareaRef.current
      if (ta) ta.selectionStart = ta.selectionEnd = ta.value.length
    }, 0)
  }, [])

  return (
    <div className="app-canvas" style={{
      display: 'grid',
      gridTemplateColumns: 'var(--rail) var(--sidebar) minmax(520px, 1fr) var(--rightbar)',
      height: '100vh', minHeight: 0, overflow: 'hidden',
    }}
      onClick={() => showModelMenu && setShowModelMenu(false)}
    >
      <Rail sessionCount={chats.length} />

      <SessionSidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={handleNewChat}
        onCloseChat={handleCloseChat}
      />

      <main style={{
        position: 'relative', minWidth: 0,
        display: 'flex', flexDirection: 'column',
        minHeight: 0, overflow: 'hidden',
        borderRight: '1px solid var(--border)',
      }}>
        <TopBar
          activeModel={activeModel}
          models={availableModels}
          onSelectModel={handleSelectModel}
          showModelMenu={showModelMenu}
          setShowModelMenu={setShowModelMenu}
          isStreaming={isStreaming}
          activeChat={activeChat}
          kittyMood={kittyMood}
        />

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {!activeChat || activeChat.messages.length === 0 ? (
            <BriefPanel
              chats={chats}
              onSelectChat={id => { setActiveChatId(id) }}
              onPrompt={handlePrompt}
              brief={brief}
            />
          ) : (
            <div style={{ paddingBottom: 140 }}>
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
          voiceEnabled={voiceEnabled}
          onVoiceToggle={() => setVoiceEnabled(v => !v)}
        />
      </main>

      <RightBar
        chats={chats}
        activeChat={activeChat}
        isStreaming={isStreaming}
        brief={brief}
        search={searchSnapshot}
        activeModelName={activeModel.name}
      />
    </div>
  )
}
