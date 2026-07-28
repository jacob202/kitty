'use client'
import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type {
  Chat,
  Message,
  MessageAttachment,
  MemoryEvidence,
  Model,
  ChatColor,
} from '@/lib/types'
import { MODELS, COLOR_CYCLE } from '@/lib/types'
import { streamChat } from '@/lib/chat-client'
import { inferMood } from '@/lib/mood'
import { useKittyState } from '@/hooks/useKittyState'
import {
  buildGatewayModels,
  fetchGatewaySearch,
  uploadCaptureFile,
  type GatewaySearchSnapshot,
  type GatewayTriageEntry,
  type ExpertProfile,
} from '@/lib/gateway'
import { validateAttachments, type AttachmentError } from '@/lib/attachment-validation'
import { normalizeMemoryEvidence } from '@/lib/types'
import { usePwaInstall } from '@/lib/pwa'
import { REDIRECTS } from '@/lib/views'
import {
  useGatewayBrief,
  useGatewayModels,
  useGatewayRuntimeManifest,
  useActiveProject,
  useProjects,
  useSetActiveProject,
  useLoops,
  useInsights,
  usePrompts,
  useToggleLoop,
  useDismissInsight,
  hasActiveBuilderRun,
} from '@/lib/queries'
import type { CatState } from '@/components/CrayonCat'

const MOBILE_BREAKPOINT = 900

let chatCounter = 0
function newChatId() { return `chat-${++chatCounter}-${Date.now()}` }
function newMsgId() { return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}` }

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

function buildExpertSystemPrompt(expert: { label: string; tags: string[]; book_count: number; sample_title: string }): string {
  const tagList = expert.tags.length > 0 ? expert.tags.join(', ') : 'general knowledge'
  return `You are acting as ${expert.label}, a specialized AI with deep expertise in ${tagList}.
Your knowledge is drawn from ${expert.book_count} reference texts.
Sample domain: ${expert.sample_title}.

Respond with the depth and precision expected of a specialist in this field.
Always cite specific frameworks, principles, or techniques from your knowledge base when relevant.
Maintain the conversational tone and intellectual rigor of a trusted advisor.`
}

interface RecoveredMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: number
  model?: string | null
  status?: string
  attachments?: MessageAttachment[]
  memory_items?: unknown
}

function legacyChat(c: Chat): Chat {
  return {
    ...c,
    createdAt: new Date(c.createdAt),
    updatedAt: new Date(c.updatedAt),
    messages: (c.messages ?? []).map((m: Message) => {
      const memoryItems = normalizeMemoryEvidence(m.memoryItems)
      return {
        ...m,
        timestamp: new Date(m.timestamp),
        ...(memoryItems.length ? { memoryItems } : {}),
      }
    }),
  }
}

const SMALLTALK_PATTERNS = [
  /^(what can you do|what do you do|who are you|how are you|good morning|good evening|good night|hello|hi|hey|yo)\b/i,
  /^(ok|okay|k|thanks|thx|thank you|got it|nice|cool)$/i,
  /^test/i,
]

function isSmalltalk(text: string): boolean {
  const sanitized = text.trim().toLowerCase()
  return SMALLTALK_PATTERNS.some((re) => re.test(sanitized))
}

function getInitials(email?: string): string {
  if (!email) return 'JB'
  const parts = email.replace(/@.*/, '').split(/[._-]/)
  return parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '').join('') || 'ME'
}

const USER_INITIALS = getInitials('jacobbrizinski@gmail.com')

function latestSearchQuery(chat: Chat | null): string {
  if (!chat) return ''
  const lastUser = [...chat.messages].reverse().find((m) => m.role === 'user')?.content?.trim()
  if (lastUser) return lastUser
  if (chat.title !== 'new chat') return chat.title.trim()
  return ''
}

// ── context shape ─────────────────────────────────────────────────────────────

interface KittyContextValue {
  // chat
  chats: Chat[]
  activeChat: Chat | null
  activeChatId: string | null
  handleNewChat: () => void
  handleNewExpertChat: (expert: ExpertProfile) => void
  handleSelectChat: (id: string) => void
  handleCloseChat: (id: string) => void
  handleSend: () => Promise<void>
  handleStop: () => void
  handleRetry: () => void

  // input
  input: string
  setInput: (v: string) => void
  attachments: MessageAttachment[]
  setAttachments: React.Dispatch<React.SetStateAction<MessageAttachment[]>>
  handleAddFiles: (files: FileList) => Promise<void>
  handleRemoveAttachment: (id: string) => void
  attachmentErrors: AttachmentError[]
  isStreaming: boolean

  // model
  activeModel: Model
  availableModels: Model[]
  overrideModel: Model | null
  setOverrideModel: React.Dispatch<React.SetStateAction<Model | null>>
  handleSelectModel: (m: Model) => void

  // persistence
  persistChat: (chat: Chat) => Promise<boolean>

  // view & shell
  activeView: string
  setActiveView: (v: string) => void
  theme: 'cosmic' | 'day' | 'night'
  setTheme: React.Dispatch<React.SetStateAction<'cosmic' | 'day' | 'night'>>
  handleToggleTheme: () => void
  isMobile: boolean
  sidebarCollapsed: boolean
  mobileSidebarOpen: boolean
  setMobileSidebarOpen: (v: boolean) => void
  handleToggleSidebar: () => void
  showOnboarding: boolean
  setShowOnboarding: (v: boolean) => void
  preferredName: string
  setPreferredName: (v: string) => void

  // status
  saveState: 'idle' | 'saving' | 'saved' | 'failed' | 'offline'
  handleRetrySave: () => void
  tokenCount: number
  lastOutcome: 'done' | 'broke' | null
  catState: CatState
  searchSnapshot: GatewaySearchSnapshot | null
  searchGateway: { live: boolean; error: string | null }

  // project
  activeProject: any
  projects: any[]
  handleSelectProject: (id: number) => void

  // gateway data
  modelsQuery: ReturnType<typeof useGatewayModels>
  runtimeQuery: ReturnType<typeof useGatewayRuntimeManifest>
  projectsQuery: ReturnType<typeof useProjects>
  activeProjectQuery: ReturnType<typeof useActiveProject>
  setActiveProject: ReturnType<typeof useSetActiveProject>
  briefQuery: ReturnType<typeof useGatewayBrief>
  loopsQuery: ReturnType<typeof useLoops>
  insightsQuery: ReturnType<typeof useInsights>
  promptsQuery: ReturnType<typeof usePrompts>
  toggleLoop: ReturnType<typeof useToggleLoop>
  dismissInsight: ReturnType<typeof useDismissInsight>

  modelGateway: { loaded: boolean; live: boolean; error: string | null }
  briefGateway: { loaded: boolean; live: boolean; error: string | null }

  // derived
  loops: any[]
  insights: any[]
  promptTemplates: any[]
  retryGatewayBootstrap: () => void

  // actions
  handleDecideInChat: (entry: GatewayTriageEntry) => void
  handleLoopToggle: (id: string) => void
  handleInsightDismiss: (id: string) => void
  handleInsightAction: (id: string, actionId: string) => void
  handlePromptSelect: (text: string) => void
  handleObjectiveSaved: (chatId: string, objective: string | null) => void
  handleRuntimeSend: (text: string) => void

  // pwa
  pwaInstall: ReturnType<typeof usePwaInstall>

  // refs
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
}

const KittyContext = createContext<KittyContextValue | null>(null)

export function useKitty(): KittyContextValue {
  const ctx = useContext(KittyContext)
  if (!ctx) throw new Error('useKitty must be used within KittyProvider')
  return ctx
}

// ── provider ──────────────────────────────────────────────────────────────────

export function KittyProvider({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const [chats, setChats] = useState<Chat[]>(() => [makeChat('teal')])
  const [activeView, setRawView] = useState('home')
  const setActiveView = useCallback((v: string) => setRawView(REDIRECTS[v] ?? v), [])
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeModel, setActiveModel] = useState<Model>(MODELS[0])

  const [tokenCount, setTokenCount] = useState(0)
  const [searchSnapshot, setSearchSnapshot] = useState<GatewaySearchSnapshot | null>(null)
  const [searchGateway, setSearchGateway] = useState<{ live: boolean; error: string | null }>({ live: true, error: null })
  const [kittyMode, setKittyMode] = useState('default')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [theme, setTheme] = useState<'cosmic' | 'day' | 'night'>('cosmic')
  const [preferredName, setPreferredName] = useState('')
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'failed' | 'offline'>('idle')
  const [lastOutcome, setLastOutcome] = useState<'done' | 'broke' | null>(null)
  const [attachments, setAttachments] = useState<MessageAttachment[]>([])
  const [overrideModel, setOverrideModel] = useState<Model | null>(null)
  const [attachmentErrors, setAttachmentErrors] = useState<AttachmentError[]>([])

  const pwaInstall = usePwaInstall()
  const abortRef = useRef<AbortController | null>(null)
  const colorIndexRef = useRef(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // gateway queries
  const queryClient = useQueryClient()
  const modelsQuery = useGatewayModels()
  const runtimeQuery = useGatewayRuntimeManifest()
  const projectsQuery = useProjects()
  const activeProjectQuery = useActiveProject()
  const setActiveProjectMut = useSetActiveProject()
  const briefQuery = useGatewayBrief()
  const loopsQuery = useLoops()
  const insightsQuery = useInsights()
  const promptsQuery = usePrompts()
  const toggleLoop = useToggleLoop()
  const dismissInsight = useDismissInsight()

  const activeChat = chats.find((c) => c.id === activeChatId) ?? chats[0] ?? null
  const userMessageCount = activeChat?.messages.filter((m) => m.role === 'user').length ?? 0

  const searchQuery = useMemo(() => latestSearchQuery(activeChat), [activeChatId, userMessageCount])

  const runtimeModelIds = runtimeQuery.data?.inference.available_models.value
  const availableModels = useMemo(
    () => runtimeModelIds ? buildGatewayModels(runtimeModelIds) : modelsQuery.data?.models ?? MODELS,
    [runtimeModelIds, modelsQuery.data?.models],
  )

  const modelGateway = {
    loaded: modelsQuery.isFetched,
    live: runtimeQuery.isSuccess
      && runtimeQuery.data?.inference.available_models.state === 'available'
      && modelsQuery.data?.fromLiveGateway === true,
    error: modelsQuery.data?.error ?? null,
  }
  const briefGateway = {
    loaded: briefQuery.isFetched,
    live: briefQuery.data?.fromLiveGateway ?? true,
    error: briefQuery.data?.error ?? null,
  }

  const loops = loopsQuery.data?.loops ?? []
  const insights = insightsQuery.data?.insights ?? []
  const promptTemplates = promptsQuery.data ?? []
  const activeProject = activeProjectQuery.data?.project ?? null
  const projects = projectsQuery.data ?? []

  const catState = useKittyState({
    isStreaming,
    lastError: lastOutcome === 'broke',
    builderActive: runtimeQuery.data ? hasActiveBuilderRun(runtimeQuery.data) : false,
  })

  // ── effects ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    fetch('/proxy/chats')
      .then((r) => (r.ok ? r.json() : null))
      .then(async (d) => {
        const saved: Chat[] = d?.chats ?? []
        if (!saved.length) return
        const recovered = await Promise.all(saved.map(async (c: Chat) => {
          try {
            const res = await fetch(`/proxy/chats/${encodeURIComponent(c.id)}/messages`)
            if (!res.ok) return legacyChat(c)
            const payload = await res.json()
            const ledgerMessages = payload?.messages ?? []
            if (!ledgerMessages.length) return legacyChat(c)
            return {
              ...c,
              createdAt: new Date(c.createdAt),
              updatedAt: new Date(c.updatedAt),
              messages: ledgerMessages.map((m: RecoveredMessage) => {
                const memoryItems = normalizeMemoryEvidence(m.memory_items)
                return {
                  id: m.id,
                  role: m.role,
                  content: m.content,
                  timestamp: new Date(m.created_at * 1000),
                  ...(m.model ? { model: m.model } : {}),
                  ...(m.status ? { turnStatus: m.status as Message['turnStatus'] } : {}),
                  ...(m.attachments?.length ? { attachments: m.attachments as MessageAttachment[] } : {}),
                  ...(memoryItems.length ? { memoryItems } : {}),
                }
              }),
            }
          } catch { return legacyChat(c) }
        }))
        const ordered = [...recovered].sort(
(a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
)
setChats(ordered)
const remembered = window.localStorage.getItem('kitty-active-chat-id')
setActiveChatId(
remembered && ordered.some((chat) => chat.id === remembered)
  ? remembered
  : ordered[0]?.id ?? null,
)
})
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const media = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`)
    const sync = () => setIsMobile(media.matches)
    sync()
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', sync)
      return () => media.removeEventListener('change', sync)
    }
    media.addListener(sync)
    return () => media.removeListener(sync)
  }, [])

  useEffect(() => {
    if (!isMobile) setMobileSidebarOpen(false)
  }, [isMobile])

  useEffect(() => {
    const savedTheme = window.localStorage.getItem('kitty-theme')
    const savedName = window.localStorage.getItem('kitty-preferred-name')
    setPreferredName(savedName ?? '')
    if (savedTheme === 'cosmic' || savedTheme === 'day' || savedTheme === 'night') {
      setTheme(savedTheme)
      document.documentElement.setAttribute('data-theme', savedTheme)
    }
    const hasLocal = window.localStorage.getItem('kitty-onboarded') === 'true'
    if (hasLocal) { setShowOnboarding(false); return }
    fetch('/proxy/onboarding')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.onboarded) {
          setShowOnboarding(false)
          if (d.preferredName) setPreferredName(d.preferredName)
          if (d.theme) { setTheme(d.theme); document.documentElement.setAttribute('data-theme', d.theme) }
          window.localStorage.setItem('kitty-onboarded', 'true')
          if (d.preferredName) window.localStorage.setItem('kitty-preferred-name', d.preferredName)
          if (d.theme) window.localStorage.setItem('kitty-theme', d.theme)
        } else { setShowOnboarding(true) }
      })
      .catch(() => { setShowOnboarding(!hasLocal) })
  }, [])

  useEffect(() => {
if (chats.length > 0 && !activeChatId) setActiveChatId(chats[0].id)
}, [chats, activeChatId])

useEffect(() => {
if (activeChatId) window.localStorage.setItem('kitty-active-chat-id', activeChatId)
}, [activeChatId])

  useEffect(() => {
    if (!availableModels.length) return
    setActiveModel((current) => availableModels.find((m) => m.id === current.id) ?? availableModels[0] ?? current)
  }, [availableModels])

  useEffect(() => {
    if (!searchQuery) { setSearchSnapshot(null); setSearchGateway({ live: true, error: null }); return }
    const controller = new AbortController()
    const timeoutId = window.setTimeout(async () => {
      const payload = await fetchGatewaySearch(searchQuery, 3, controller.signal)
      if (controller.signal.aborted) return
      startTransition(() => {
        setSearchSnapshot(payload.snapshot)
        setSearchGateway({ live: payload.fromLiveGateway, error: payload.error })
      })
    }, 400)
    return () => { clearTimeout(timeoutId); controller.abort() }
  }, [searchQuery])

  useEffect(() => {
    if (!activeChat) return
    const chars = activeChat.messages.reduce((sum, m) => sum + m.content.length, 0)
    setTokenCount(Math.round(chars / 4))
  }, [activeChat?.messages])

  // ── handlers ─────────────────────────────────────────────────────────────────

  const handleNewChat = useCallback(() => {
    const color = COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length]
    colorIndexRef.current++
    const chat = makeChat(color)
    chat.model = activeModel.id
    setChats((prev) => [...prev, chat])
    setActiveChatId(chat.id)
    setInput('')
  }, [activeModel.id])

  const handleNewExpertChat = useCallback((expert: ExpertProfile) => {
    const color = COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length]
    colorIndexRef.current++
    const chat = makeChat(color)
    chat.model = activeModel.id
    chat.title = `chat with ${expert.label}`
    chat.expertId = expert.id
    chat.systemPrompt = buildExpertSystemPrompt(expert)
    setChats((prev) => [...prev, chat])
    setActiveChatId(chat.id)
    setInput('')
  }, [activeModel.id])

  const handleToggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === 'cosmic' ? 'day' : t === 'day' ? 'night' : 'cosmic'
      document.documentElement.setAttribute('data-theme', next)
      window.localStorage.setItem('kitty-theme', next)
      return next
    })
  }, [])

  const handleToggleSidebar = useCallback(() => {
    if (isMobile) { setMobileSidebarOpen((o) => !o); return }
    setSidebarCollapsed((c) => !c)
  }, [isMobile])

  const handleSelectChat = useCallback((id: string) => {
    setActiveChatId(id)
    if (isMobile) setMobileSidebarOpen(false)
  }, [isMobile])

  const handleSidebarNewChat = useCallback(() => {
    handleNewChat()
    if (isMobile) setMobileSidebarOpen(false)
  }, [handleNewChat, isMobile])

  const handleCloseChat = useCallback((id: string) => {
    setChats((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (next.length === 0) {
        const fresh = makeChat(COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length])
        colorIndexRef.current++
        return [fresh]
      }
      return next
    })
    setActiveChatId((prev) => {
      if (prev !== id) return prev
      const remaining = chats.filter((c) => c.id !== id)
      return remaining[remaining.length - 1]?.id ?? null
    })
  }, [chats])

  const handleSelectModel = useCallback((m: Model) => {
    setActiveModel(m)
    if (activeChat) setChats((prev) => prev.map((c) => (c.id === activeChat.id ? { ...c, model: m.id } : c)))
  }, [activeChat])

  const updateChat = useCallback((id: string, updater: (c: Chat) => Chat) => {
    setChats((prev) => prev.map((c) => (c.id === id ? updater(c) : c)))
  }, [])

  const persistChat = useCallback(async (chat: Chat): Promise<boolean> => {
    setSaveState('saving')
    try {
      const res = await fetch('/proxy/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chat),
      })
      if (res.ok) { setSaveState('saved'); return true }
      setSaveState(res.status >= 500 ? 'offline' : 'failed')
      return false
    } catch { setSaveState('offline'); return false }
  }, [])

  const handleObjectiveSaved = useCallback((chatId: string, objective: string | null) => {
    updateChat(chatId, (c) => ({ ...c, objective: objective ?? undefined }))
  }, [updateChat])

  const handleRetrySave = useCallback(() => {
    const chat = chats.find((c) => c.id === activeChatId)
    if (chat) void persistChat(chat)
  }, [chats, activeChatId, persistChat])

  const runStream = useCallback(async (chat: Chat, history: Message[], title: string, attachmentIds: string[] = [], modelOverride?: Model) => {
    const latestUserMessage = [...history].reverse().find((m) => m.role === 'user')
    if (!latestUserMessage) throw new Error('Cannot start a chat turn without a user message')
    const turnModel = modelOverride ?? activeModel
    setIsStreaming(true)
    setLastOutcome(null)

    const aiMsgId = newMsgId()
    const aiMsg: Message = { id: aiMsgId, role: 'assistant', content: '', timestamp: new Date(), model: turnModel.name }
    updateChat(chat.id, (c) => ({ ...c, messages: [...history, aiMsg] }))

    const abort = new AbortController()
    abortRef.current = abort
    let accumulated = ''
    let memoryItems: MemoryEvidence[] | undefined
    let toolCalls: import('@/lib/types').ToolCall[] | undefined
    let provider: string | undefined
    let requestedModel: string | undefined
    let toolsState: 'available' | 'unavailable' | undefined
    try {
      for await (const chunk of streamChat(turnModel.id, history, abort.signal, activeProject?.id, chat.id, latestUserMessage.id, title, attachmentIds)) {
        if (chunk.done) break
        if (chunk.provider || chunk.requestedModel || chunk.toolsState) {
          provider = chunk.provider ?? provider
          requestedModel = chunk.requestedModel ?? requestedModel
          toolsState = chunk.toolsState ?? toolsState
          updateChat(chat.id, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, provider, requestedModel, toolsState } : m)) }))
          continue
        }
        if (chunk.memoryItems?.length) { memoryItems = chunk.memoryItems; continue }
        if (chunk.toolCalls?.length) {
          toolCalls = chunk.toolCalls
          updateChat(chat.id, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, toolCalls } : m)) }))
          continue
        }
        accumulated += chunk.content
        updateChat(chat.id, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, content: accumulated } : m)) }))
      }
      const mood = inferMood(accumulated, 'assistant')
      const extras = {
        ...(memoryItems && !isSmalltalk(latestUserMessage.content) ? { memoryItems } : {}),
        ...(toolCalls?.length ? { toolCalls } : {}),
        ...(provider ? { provider } : {}),
        ...(requestedModel ? { requestedModel } : {}),
        ...(toolsState ? { toolsState } : {}),
      }
      updateChat(chat.id, (c) => ({ ...c, updatedAt: new Date(), messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, content: accumulated, mood, ...extras } : m)) }))
      setLastOutcome('done')
      window.setTimeout(() => setLastOutcome((o) => (o === 'done' ? null : o)), 2500)
      void persistChat({ id: chat.id, title, model: turnModel.id, color: chat.color, createdAt: chat.createdAt, updatedAt: new Date(), messages: [...history, { ...aiMsg, content: accumulated, mood, ...extras }] })
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        const interruptedContent = accumulated ? `${accumulated}\n\n⚠ generation stopped before completion.` : '⚠ generation stopped before Kitty returned a response.'
        const interruptedMessage: Message = { ...aiMsg, content: interruptedContent, mood: 'confused', turnStatus: 'interrupted' }
        updateChat(chat.id, (c) => ({ ...c, updatedAt: new Date(), messages: c.messages.map((m) => (m.id === aiMsgId ? interruptedMessage : m)) }))
        void persistChat({ id: chat.id, title, model: turnModel.id, color: chat.color, createdAt: chat.createdAt, updatedAt: new Date(), messages: [...history, interruptedMessage] })
        return
      }
      setLastOutcome('broke')
      updateChat(chat.id, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, content: `⚠ ${err instanceof Error ? err.message : 'error connecting to gateway'}`, mood: 'confused' as const } : m)) }))
      void persistChat({ id: chat.id, title, model: turnModel.id, color: chat.color, createdAt: chat.createdAt, updatedAt: new Date(), messages: history })
    } finally { setIsStreaming(false); abortRef.current = null }
  }, [activeModel, activeProject?.id, updateChat, persistChat])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isStreaming || !activeChat) return
    const userMsg: Message = { id: newMsgId(), role: 'user', content: text, timestamp: new Date(), attachments: attachments.length ? [...attachments] : undefined }
    const isFirst = activeChat.messages.length === 0
    const title = isFirst ? text.slice(0, 32) + (text.length > 32 ? '…' : '') : activeChat.title
    updateChat(activeChat.id, (c) => ({ ...c, title, messages: [...c.messages, userMsg], updatedAt: new Date() }))
    setInput('')
    setAttachments([])
    const attachmentIds = attachments.map((a) => a.id)
    const oneShot = overrideModel ?? undefined
    setOverrideModel(null)
    void runStream(activeChat, [...activeChat.messages, userMsg], title, attachmentIds, oneShot)
  }, [input, isStreaming, activeChat, runStream, overrideModel, attachments, updateChat])

  const handleRetry = useCallback(() => {
    if (!activeChat || isStreaming) return
    const history = [...activeChat.messages]
    while (history.length && history.at(-1)?.role === 'assistant') history.pop()
    if (history.length === 0) return
    updateChat(activeChat.id, (c) => ({ ...c, messages: history }))
    void runStream(activeChat, history, activeChat.title)
  }, [activeChat, isStreaming, updateChat, runStream])

  const handleStop = useCallback(() => { abortRef.current?.abort() }, [])

  const handleRuntimeSend = useCallback((text: string) => {
    if (!text.trim() || isStreaming || !activeChat) return
    const userMsg: Message = { id: newMsgId(), role: 'user', content: text.trim(), timestamp: new Date() }
    const isFirst = activeChat.messages.length === 0
    const title = isFirst ? text.slice(0, 32) + (text.length > 32 ? '…' : '') : activeChat.title
    updateChat(activeChat.id, (c) => ({ ...c, title, messages: [...c.messages, userMsg], updatedAt: new Date() }))
    setInput('')
    setAttachments([])
    void runStream(activeChat, [...activeChat.messages, userMsg], title)
  }, [isStreaming, activeChat, updateChat, runStream])

  const handlePromptSelect = useCallback((text: string) => {
    setInput(text)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [])

  const handleAddFiles = useCallback(async (files: FileList) => {
    if (!activeChat) return
    const { valid, errors } = validateAttachments(files)
    if (errors.length) setAttachmentErrors(errors)
    else setAttachmentErrors([])
    const added: MessageAttachment[] = []
    for (const file of valid) {
      const result = await uploadCaptureFile(file, { conversationId: activeChat.id, projectId: activeProject?.id })
      if (result?.artifact_id) added.push({ id: result.artifact_id, display_name: file.name, media_type: file.type || 'application/octet-stream', size: file.size })
    }
    if (added.length) setAttachments((prev) => [...prev, ...added])
  }, [activeChat, activeProject?.id])

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const handleDecideInChat = useCallback((entry: GatewayTriageEntry) => {
    handlePromptSelect(`Help me decide what to do with this: ${entry.text ?? `inbox entry ${entry.inbox_id}`}`)
  }, [handlePromptSelect])

  const handleLoopToggle = useCallback((id: string) => { toggleLoop.mutate(id) }, [toggleLoop])
  const handleInsightDismiss = useCallback((id: string) => { dismissInsight.mutate(id) }, [dismissInsight])
  const handleInsightAction = useCallback((_id: string, _actionId: string) => {}, [])

  const handleSelectProject = useCallback((id: number) => setActiveProjectMut.mutate(id), [setActiveProjectMut])

  const retryGatewayBootstrap = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['models'] })
    queryClient.invalidateQueries({ queryKey: ['brief'] })
    queryClient.invalidateQueries({ queryKey: ['state'] })
    queryClient.invalidateQueries({ queryKey: ['actions'] })
    queryClient.invalidateQueries({ queryKey: ['todos'] })
    queryClient.invalidateQueries({ queryKey: ['inbox'] })
    queryClient.invalidateQueries({ queryKey: ['loops'] })
    queryClient.invalidateQueries({ queryKey: ['insights'] })
    queryClient.invalidateQueries({ queryKey: ['prompts'] })
  }, [queryClient])

  if (!mounted) {
    return <div style={{ height: '100dvh', background: 'var(--bg)' }} />
  }

  const value: KittyContextValue = {
    chats, activeChat, activeChatId, handleNewChat, handleNewExpertChat, handleSelectChat, handleCloseChat,
    handleSend, handleStop, handleRetry,
    input, setInput, attachments, setAttachments, handleAddFiles, handleRemoveAttachment,
    attachmentErrors, isStreaming,
    activeModel, availableModels, overrideModel, setOverrideModel, handleSelectModel,
    persistChat,
    activeView, setActiveView, theme, setTheme, handleToggleTheme, isMobile, sidebarCollapsed,
    mobileSidebarOpen, setMobileSidebarOpen, handleToggleSidebar,
    showOnboarding, setShowOnboarding, preferredName, setPreferredName,
    saveState, handleRetrySave, tokenCount, lastOutcome, catState,
    searchSnapshot, searchGateway,
    activeProject, projects, handleSelectProject,
    modelsQuery, runtimeQuery, projectsQuery, activeProjectQuery, setActiveProject: setActiveProjectMut,
    briefQuery, loopsQuery, insightsQuery, promptsQuery, toggleLoop, dismissInsight,
    modelGateway, briefGateway,
    loops, insights, promptTemplates, retryGatewayBootstrap,
    handleDecideInChat, handleLoopToggle, handleInsightDismiss, handleInsightAction,
    handlePromptSelect, handleObjectiveSaved, handleRuntimeSend,
    pwaInstall, textareaRef,
  }

  return <KittyContext.Provider value={value}>{children}</KittyContext.Provider>
}
