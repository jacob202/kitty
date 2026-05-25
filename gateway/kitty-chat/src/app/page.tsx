'use client'
import { startTransition, useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Chat, Message, Model, MODELS, COLOR_CYCLE, ChatColor } from '@/lib/types'
import { streamChat } from '@/lib/openwebui'
import { inferMood } from '@/lib/mood'
import { TopBar } from '@/components/TopBar'
import { ChatMessage } from '@/components/ChatMessage'
import { InputBar } from '@/components/InputBar'
import { DashboardHome } from '@/components/DashboardHome'
import { Rail } from '@/components/Rail'
import { SessionSidebar } from '@/components/SessionSidebar'
import { RightPanel } from '@/components/RightPanel'
import { TaskPanel } from '@/components/TaskPanel'
import { TodoPanel } from '@/components/TodoPanel'
import { TerminalStrip } from '@/components/TerminalStrip'
import {
  fetchGatewayBrief,
  fetchGatewayModels,
  fetchGatewaySearch,
  fetchGatewayTodos,
  fetchGatewayLoops,
  fetchGatewayInsights,
  fetchGatewayPrompts, fetchGatewayWeather,
  toggleGatewayLoop,
  dismissGatewayInsight,
  type GatewayBrief,
  type GatewaySearchSnapshot,
  type GatewayTodo,
  type GatewayLoop,
  type GatewayInsight, type GatewayWeather,
  type GatewayPromptTemplate,
} from '@/lib/gateway'

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
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  if (!mounted) {
    return <div style={{ height: '100vh', background: 'var(--bg)' }} />
  }

  return <KittyChatInner />
}

function KittyChatInner() {
  const [chats, setChats] = useState<Chat[]>(() => [makeChat('teal')])
  const [activeView, setActiveView] = useState('home')
  const [activeChatId, setActiveChatId] = useState<string | null>(() => null)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [availableModels, setAvailableModels] = useState<Model[]>(MODELS)
  const [activeModel, setActiveModel] = useState<Model>(MODELS[0])
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [tokenCount, setTokenCount] = useState(0)
  const [brief, setBrief] = useState<GatewayBrief | null>(null)
  const [todos, setTodos] = useState<GatewayTodo[]>([])
  const [weather, setWeather] = useState<GatewayWeather | null>(null)
  const [loops, setLoops] = useState<GatewayLoop[]>([])
  const [insights, setInsights] = useState<GatewayInsight[]>([])
  const [promptTemplates, setPromptTemplates] = useState<GatewayPromptTemplate[]>([])
  const [searchSnapshot, setSearchSnapshot] = useState<GatewaySearchSnapshot | null>(null)
  const [modelGateway, setModelGateway] = useState<{
    loaded: boolean
    live: boolean
    error: string | null
  }>({ loaded: false, live: true, error: null })
  const [briefGateway, setBriefGateway] = useState<{
    loaded: boolean
    live: boolean
    error: string | null
  }>({ loaded: false, live: true, error: null })
  const [searchGateway, setSearchGateway] = useState<{
    live: boolean
    error: string | null
  }>({ live: true, error: null })
  const [gwReload, setGwReload] = useState(0)
  const [kittyMode, setKittyMode] = useState('default')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const colorIndexRef = useRef(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const activeChat = chats.find(c => c.id === activeChatId) ?? chats[0] ?? null
  const userMessageCount = activeChat?.messages.filter(m => m.role === 'user').length ?? 0
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const searchQuery = useMemo(() => latestSearchQuery(activeChat), [activeChatId, userMessageCount])

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
      const modelsPayload = await fetchGatewayModels()
      if (cancelled) return

      startTransition(() => {
        setModelGateway({
          loaded: true,
          live: modelsPayload.fromLiveGateway,
          error: modelsPayload.error,
        })
        setAvailableModels(modelsPayload.models)
        setActiveModel(current =>
          modelsPayload.models.find(model => model.id === current.id) ?? modelsPayload.models[0] ?? current,
        )
      })

      const briefPayload = await fetchGatewayBrief()
      if (cancelled) return
      startTransition(() => {
        setBriefGateway({
          loaded: true,
          live: briefPayload.fromLiveGateway,
          error: briefPayload.error,
        })
        setBrief(briefPayload.brief)
      })

      const todoList = await fetchGatewayTodos()
      if (cancelled) return
      startTransition(() => {
        setTodos(todoList)
      })

      const weatherPayload = await fetchGatewayWeather()
      if (cancelled) return
      startTransition(() => {
        setWeather(weatherPayload.weather)
      })

      const loopsPayload = await fetchGatewayLoops()
      if (cancelled) return
      startTransition(() => {
        setLoops(loopsPayload.loops)
      })

      const insightsPayload = await fetchGatewayInsights()
      if (cancelled) return
      startTransition(() => {
        setInsights(insightsPayload.insights)
      })

      const promptsPayload = await fetchGatewayPrompts()
      if (cancelled) return
      startTransition(() => {
        setPromptTemplates(promptsPayload)
      })
    })()

    return () => {
      cancelled = true
    }
  }, [gwReload])

  useEffect(() => {
    if (!searchQuery) {
      setSearchSnapshot(null)
      setSearchGateway({ live: true, error: null })
      return
    }

    const controller = new AbortController()

    const timeoutId = window.setTimeout(async () => {
      const payload = await fetchGatewaySearch(searchQuery, 3, controller.signal)
      if (controller.signal.aborted) return
      startTransition(() => {
        setSearchSnapshot(payload.snapshot)
        setSearchGateway({ live: payload.fromLiveGateway, error: payload.error })
      })
    }, 400)

    return () => {
      clearTimeout(timeoutId)
      controller.abort()
    }
  }, [searchQuery])

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
    setActiveView('chat')
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
      updateChat(activeChat.id, c => ({
        ...c,
        messages: c.messages.map(m =>
          m.id === aiMsgId
            ? { ...m, content: `⚠ ${err instanceof Error ? err.message : 'Error connecting to gateway'}`, mood: 'confused' as const }
            : m
        ),
      }))
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [input, isStreaming, activeChat, activeModel, updateChat])

  const retryGatewayBootstrap = useCallback(() => {
    setModelGateway({ loaded: false, live: true, error: null })
    setBriefGateway({ loaded: false, live: true, error: null })
    setGwReload(n => n + 1)
  }, [])

  const handlePrompt = useCallback((text: string) => {
    setInput(text)
    setTimeout(() => {
      textareaRef.current?.focus()
      const ta = textareaRef.current
      if (ta) ta.selectionStart = ta.selectionEnd = ta.value.length
    }, 0)
  }, [])

  const handleLoopToggle = useCallback((loopId: string) => {
    void (async () => {
      await toggleGatewayLoop(loopId)
      setGwReload(n => n + 1)
    })()
  }, [])

  const handleInsightDismiss = useCallback((insightId: string) => {
    void (async () => {
      await dismissGatewayInsight(insightId)
      setInsights(prev => prev.filter(i => i.insight_id !== insightId))
    })()
  }, [])

  const handleInsightAction = useCallback((_insightId: string, _actionId: string) => {
  }, [])

  return (
    <div className="app-canvas" style={{
      display: 'grid',
      gridTemplateColumns: `var(--rail) ${sidebarCollapsed ? '60px' : 'var(--sidebar)'} minmax(520px, 1fr) var(--rightbar)`,
      transition: 'grid-template-columns 0.2s ease',
      height: '100vh', minHeight: 0, overflow: 'hidden',
    }}
      onClick={() => showModelMenu && setShowModelMenu(false)}
    >
      <Rail activeView={activeView} onViewChange={setActiveView} />

       <SessionSidebar
         chats={chats}
         activeChatId={activeChatId}
         onSelectChat={setActiveChatId}
         onNewChat={handleNewChat}
         onCloseChat={handleCloseChat}
         collapsed={sidebarCollapsed}
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
          modelFromGateway={modelGateway.live}
          activeView={activeView}
          onViewChange={setActiveView}
          kittyMode={kittyMode}
          onKittyModeChange={setKittyMode}
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {modelGateway.loaded && !modelGateway.live && (
          <div
            role="status"
            style={{
              padding: '4px 16px',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-muted)',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexShrink: 0,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--error)', flexShrink: 0, display: 'inline-block' }} />
              gateway offline
            </span>
            <button
              type="button"
              onClick={retryGatewayBootstrap}
              style={{
                border: 'none',
                borderRadius: 4,
                padding: '2px 8px',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                fontWeight: 600,
                cursor: 'pointer',
                background: 'transparent',
                color: 'var(--text-muted)',
                flexShrink: 0,
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)' }}
            >
              retry
            </button>
          </div>
        )}

        {modelGateway.loaded && modelGateway.live && briefGateway.loaded && !briefGateway.live && (
          <div
            role="status"
            style={{
              padding: '6px 16px',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-dim)',
              background: 'rgba(16, 20, 29, 0.5)',
              borderBottom: '1px solid var(--border)',
              flexShrink: 0,
            }}
          >
            Brief unavailable ({briefGateway.error ?? 'unknown'}). Chat still works.
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {activeView === 'tasks' ? (
            <div style={{
              flex: 1,
              padding: '24px 32px 40px',
              display: 'grid',
              gap: 24,
              alignContent: 'start',
            }}>
              <TaskPanel />
              <TodoPanel />
            </div>
          ) : activeView === 'terminal' ? (
            <div style={{
              flex: 1,
              padding: '24px 32px 40px',
              display: 'flex',
              flexDirection: 'column',
            }}>
              <TerminalStrip title="Gateway Log" maxLines={100} />
            </div>
          ) : activeView === 'chat' && activeChat && activeChat.messages.length > 0 ? (
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
          ) : activeView === 'chat' ? (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              gap: 16, paddingBottom: 100,
            }}>
              <span style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 28,
                color: 'var(--primary)',
                opacity: 0.35,
                userSelect: 'none',
              }}>{'=^•ﻌ•^='}</span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 13,
                color: 'var(--text-ghost)',
              }}>start a conversation</span>
            </div>
          ) : activeView === 'home' ? (
            <DashboardHome
              chats={chats}
              onSelectChat={setActiveChatId}
              onPromptSelect={handlePrompt}
              brief={brief}
              todos={todos}
              weather={weather}
              loops={loops}
              insights={insights}
              promptTemplates={promptTemplates}
              loading={!briefGateway.loaded}
              onLoopToggle={handleLoopToggle}
              onInsightDismiss={handleInsightDismiss}
              onInsightAction={handleInsightAction}
            />
          ) : (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              gap: 12, fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)', fontSize: 14,
            }}>
              <span style={{ fontSize: 32, opacity: 0.3 }}>?</span>
              <span>{activeView.charAt(0).toUpperCase() + activeView.slice(1)} view</span>
              <span style={{ fontSize: 12, color: 'var(--text-ghost)' }}>coming soon</span>
            </div>
          )}
        </div>

        {(activeView === 'home' || activeView === 'chat') && (
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
        )}
      </main>

      <RightPanel
        chats={chats}
        activeChat={activeChat}
        isStreaming={isStreaming}
        brief={brief}
        search={searchSnapshot}
        searchGatewayError={searchGateway.live ? null : searchGateway.error}
        activeModelName={activeModel.name}
      />
    </div>
  )
}
