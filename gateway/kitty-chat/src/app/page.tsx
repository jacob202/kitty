'use client';
import { startTransition, useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Chat,
  Message,
  MessageAttachment,
  MemoryEvidence,
  Model,
  MODELS,
  COLOR_CYCLE,
  ChatColor,
  normalizeMemoryEvidence,
} from '@/lib/types';
import { streamChat } from '@/lib/chat-client';
import { inferMood } from '@/lib/mood';
import { TopBar } from '@/components/TopBar';
import { ThreadGoal } from '@/components/ThreadGoal';
import { SignalFeed } from '@/components/SignalCard';
import { ChatMessage } from '@/components/ChatMessage';
import { InputBar } from '@/components/InputBar';
import { HomeState } from '@/components/HomeState';
import { Rail } from '@/components/Rail';
import { SessionSidebar } from '@/components/SessionSidebar';
import { TaskPanel } from '@/components/TaskPanel';
import { TodoPanel } from '@/components/TodoPanel';
import { TerminalStrip } from '@/components/TerminalStrip';
import { AgentPanel } from '@/components/AgentPanel';
import { MonitorPanel } from '@/components/MonitorPanel';
import { ImageGenPanel } from '@/components/ImageGenPanel';
import { TutorPanel } from '@/components/TutorPanel';
import { ProjectsPanel } from '@/components/ProjectsPanel';
import { DocumentsPanel } from '@/components/DocumentsPanel';
import { ProviderCenter } from '@/components/ProviderCenter';
import { SettingsPanel } from '@/components/SettingsPanel';
import { BuilderPanel } from '@/components/BuilderSurface';
import { OnboardingModal } from '@/components/OnboardingModal';
import { LoopWatch } from '@/components/LoopWatch';
import { InsightFeed } from '@/components/InsightFeed';
import { PromptToolkit } from '@/components/PromptToolkit';
import { CommandPalette } from '@/components/CommandPalette';
import { ActiveTaskCards } from '@/components/ActiveTaskCards';
import { KittyRuntimeProvider } from '@/components/KittyRuntimeProvider';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { PwaInstallBanner } from '@/components/PwaInstallBanner';
import { WobFilters, PaperGrain } from '@/components/WobFilters';
import { CatCorner, CatBody, type CatState } from '@/components/CrayonCat';
import {
  buildGatewayModels,
  fetchGatewaySearch,
  uploadCaptureFile,
  type GatewaySearchSnapshot,
  type GatewayTriageEntry,
} from '@/lib/gateway';
import { validateAttachments, type AttachmentError } from '@/lib/attachment-validation';
import { usePwaInstall } from '@/lib/pwa';
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
} from '@/lib/queries';

const MOBILE_BREAKPOINT = 900;

let chatCounter = 0;
function newChatId() {
  return `chat-${++chatCounter}-${Date.now()}`;
}
function newMsgId() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function makeChat(color: ChatColor): Chat {
  return {
    id: newChatId(),
    title: 'new chat',
    messages: [],
    model: MODELS[0].id,
    color,
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

interface RecoveredMessage {
  id: string
  role: 'user' | 'assistant';
  content: string;
  created_at: number;
  model?: string | null;
  status?: string;
  attachments?: MessageAttachment[];
  memory_items?: unknown;
}

/** Map a saved legacy chat blob into the UI shape with Date timestamps. */
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
  };
}

function getInitials(email?: string): string {
  if (!email) return 'JB';
  const parts = email.replace(/@.*/, '').split(/[._-]/);
  return (
    parts
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? '')
      .join('') || 'ME'
  );
}

const USER_INITIALS = getInitials('jacobbrizinski@gmail.com');

function ToolCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1.5px solid var(--line)',
        borderRadius: 12,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'lowercase',
          color: 'var(--ink-2)',
          paddingBottom: 8,
          borderBottom: '1px solid var(--line)',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function panelPadding(isMobile: boolean): React.CSSProperties {
  return {
    flex: 1,
    padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
    display: 'grid',
    gap: 16,
    alignContent: 'start',
    maxWidth: 860,
    width: '100%',
    margin: '0 auto',
  };
}

function latestSearchQuery(chat: Chat | null): string {
  if (!chat) return '';
  const lastUser = [...chat.messages]
    .reverse()
    .find((message) => message.role === 'user')
    ?.content?.trim();
  if (lastUser) return lastUser;
  if (chat.title !== 'new chat') return chat.title.trim();
  return '';
}

export default function KittyChat() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div style={{ height: '100vh', background: 'var(--bg)' }} />;
  }

  return <KittyChatInner />;
}

function KittyChatInner() {
  const [chats, setChats] = useState<Chat[]>(() => [makeChat('teal')]);
  const [activeView, setActiveView] = useState('home');
  const [activeChatId, setActiveChatId] = useState<string | null>(() => null);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeModel, setActiveModel] = useState<Model>(MODELS[0]);

  const [tokenCount, setTokenCount] = useState(0);
  const [searchSnapshot, setSearchSnapshot] = useState<GatewaySearchSnapshot | null>(null);
  const [searchGateway, setSearchGateway] = useState<{
    live: boolean;
    error: string | null;
  }>({ live: true, error: null });
  const [kittyMode, setKittyMode] = useState('default');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [theme, setTheme] = useState<'cosmic' | 'day' | 'night'>('cosmic');
  const [preferredName, setPreferredName] = useState('');
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'failed' | 'offline'>(
    'idle',
  );
  const pwaInstall = usePwaInstall();
  const [lastOutcome, setLastOutcome] = useState<'done' | 'broke' | null>(null);
  const [attachments, setAttachments] = useState<MessageAttachment[]>([]);
  // CR-07: one-shot model override — applies to the next message only.
  const [overrideModel, setOverrideModel] = useState<Model | null>(null);

  const catState: CatState = isStreaming ? 'working' : (lastOutcome ?? 'idle');

  useEffect(() => {
    fetch('/proxy/chats')
      .then((r) => (r.ok ? r.json() : null))
      .then(async (d) => {
        const saved: Chat[] = d?.chats ?? [];
        if (!saved.length) return;
        const recovered = await Promise.all(
          saved.map(async (c: Chat) => {
            // Prefer the durable lifecycle ledger for history when it has
            // messages; fall back to the legacy blob otherwise. The ledger is
            // the honest source for restart recovery.
            try {
              const res = await fetch(`/proxy/chats/${encodeURIComponent(c.id)}/messages`);
              if (!res.ok) return legacyChat(c);
              const payload = await res.json();
              const ledgerMessages = payload?.messages ?? [];
              if (!ledgerMessages.length) return legacyChat(c);
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
                    ...(m.attachments?.length
                      ? { attachments: m.attachments as MessageAttachment[] }
                      : {}),
                    ...(memoryItems.length ? { memoryItems } : {}),
                  }
                }),
              };
            } catch {
              return legacyChat(c);
            }
          }),
        );
        setChats(recovered);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const media = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
    const syncViewport = () => setIsMobile(media.matches);

    syncViewport();
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', syncViewport);
      return () => media.removeEventListener('change', syncViewport);
    }

    media.addListener(syncViewport);
    return () => media.removeListener(syncViewport);
  }, []);

  useEffect(() => {
    if (!isMobile) {
      setMobileSidebarOpen(false);
    }
  }, [isMobile]);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem('kitty-theme');
    setPreferredName(window.localStorage.getItem('kitty-preferred-name') ?? '');
    if (savedTheme === 'cosmic' || savedTheme === 'day' || savedTheme === 'night') {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
    setShowOnboarding(window.localStorage.getItem('kitty-onboarded') !== 'true');
  }, []);

  // Gateway status queries — models for TopBar, brief for the offline banner.
  const queryClient = useQueryClient();
  const modelsQuery = useGatewayModels();
  const runtimeQuery = useGatewayRuntimeManifest();
  const projectsQuery = useProjects();
  const activeProjectQuery = useActiveProject();
  const setActiveProject = useSetActiveProject();
  const briefQuery = useGatewayBrief();
  // Loops/insights/prompts still bind to real data but aren't part of the
  // console home surface — they live in the Tools view instead.
  const loopsQuery = useLoops();
  const insightsQuery = useInsights();
  const promptsQuery = usePrompts();
  const toggleLoop = useToggleLoop();
  const dismissInsight = useDismissInsight();

  const runtimeModelIds = runtimeQuery.data?.inference.available_models.value;
  const availableModels = useMemo(
    () => runtimeModelIds
      ? buildGatewayModels(runtimeModelIds)
      : modelsQuery.data?.models ?? MODELS,
    [runtimeModelIds, modelsQuery.data?.models],
  );
  const modelGateway = {
    loaded: modelsQuery.isFetched,
    live:
      runtimeQuery.isSuccess
      && runtimeQuery.data?.inference.available_models.state === 'available'
      && modelsQuery.data?.fromLiveGateway === true,
    error: modelsQuery.data?.error ?? null,
  };
  const briefGateway = {
    loaded: briefQuery.isFetched,
    live: briefQuery.data?.fromLiveGateway ?? true,
    error: briefQuery.data?.error ?? null,
  };

  const loops = loopsQuery.data?.loops ?? [];
  const insights = insightsQuery.data?.insights ?? [];
  const promptTemplates = promptsQuery.data ?? [];
  const activeProject = activeProjectQuery.data?.project ?? null;
  const projects = projectsQuery.data ?? [];

  const handleSelectProject = useCallback(
    (projectId: number) => setActiveProject.mutate(projectId),
    [setActiveProject],
  );

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const colorIndexRef = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const activeChat = chats.find((c) => c.id === activeChatId) ?? chats[0] ?? null;
  const userMessageCount = activeChat?.messages.filter((m) => m.role === 'user').length ?? 0;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const searchQuery = useMemo(
    () => latestSearchQuery(activeChat),
    [activeChatId, userMessageCount],
  );

  useEffect(() => {
    if (chats.length > 0 && !activeChatId) {
      setActiveChatId(chats[0].id);
    }
  }, [chats, activeChatId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChat?.messages.length, isStreaming]);

  // Sync activeModel with the authoritative runtime model list once it loads.
  useEffect(() => {
    if (!availableModels.length) return;
    const models = availableModels;
    setActiveModel((current) => models.find((m) => m.id === current.id) ?? models[0] ?? current);
  }, [availableModels]);

  useEffect(() => {
    if (!searchQuery) {
      setSearchSnapshot(null);
      setSearchGateway({ live: true, error: null });
      return;
    }

    const controller = new AbortController();

    const timeoutId = window.setTimeout(async () => {
      const payload = await fetchGatewaySearch(searchQuery, 3, controller.signal);
      if (controller.signal.aborted) return;
      startTransition(() => {
        setSearchSnapshot(payload.snapshot);
        setSearchGateway({ live: payload.fromLiveGateway, error: payload.error });
      });
    }, 400);

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [searchQuery]);

  // rough token estimate: ~4 chars per token
  useEffect(() => {
    if (!activeChat) return;
    const chars = activeChat.messages.reduce((sum, m) => sum + m.content.length, 0);
    setTokenCount(Math.round(chars / 4));
  }, [activeChat?.messages]);

  const handleNewChat = useCallback(() => {
    const color = COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length];
    colorIndexRef.current++;
    const chat = makeChat(color);
    chat.model = activeModel.id;
    setChats((prev) => [...prev, chat]);
    setActiveChatId(chat.id);
    setInput('');
  }, [activeModel.id]);

  const handleToggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === 'cosmic' ? 'day' : t === 'day' ? 'night' : 'cosmic';
      document.documentElement.setAttribute('data-theme', next);
      window.localStorage.setItem('kitty-theme', next);
      return next;
    });
  }, []);

  const handleToggleSidebar = useCallback(() => {
    if (isMobile) {
      setMobileSidebarOpen((open) => !open);
      return;
    }
    setSidebarCollapsed((collapsed) => !collapsed);
  }, [isMobile]);

  const handleSelectChat = useCallback(
    (id: string) => {
      setActiveChatId(id);
      setActiveView('chat');
      if (isMobile) {
        setMobileSidebarOpen(false);
      }
    },
    [isMobile],
  );

  const handleSidebarNewChat = useCallback(() => {
    handleNewChat();
    setActiveView('chat');
    if (isMobile) {
      setMobileSidebarOpen(false);
    }
  }, [handleNewChat, isMobile]);

  const handleCloseChat = useCallback(
    (id: string) => {
      setChats((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (next.length === 0) {
          const fresh = makeChat(COLOR_CYCLE[colorIndexRef.current % COLOR_CYCLE.length]);
          colorIndexRef.current++;
          return [fresh];
        }
        return next;
      });
      setActiveChatId((prev) => {
        if (prev !== id) return prev;
        const remaining = chats.filter((c) => c.id !== id);
        return remaining[remaining.length - 1]?.id ?? null;
      });
    },
    [chats],
  );

  const handleSelectModel = useCallback(
    (m: Model) => {
      setActiveModel(m);
      if (activeChat) {
        setChats((prev) => prev.map((c) => (c.id === activeChat.id ? { ...c, model: m.id } : c)));
      }
    },
    [activeChat],
  );

  const updateChat = useCallback((id: string, updater: (c: Chat) => Chat) => {
    setChats((prev) => prev.map((c) => (c.id === id ? updater(c) : c)));
  }, []);

  // Persist a chat to SQLite via the gateway, tracking the outcome so the UI
  // can say saved / failed / offline instead of silently dropping history.
  // Returns whether the save landed so callers (ThreadGoal's create-then-patch
  // path) can react instead of guessing.
  const persistChat = useCallback(async (chat: Chat): Promise<boolean> => {
    setSaveState('saving');
    try {
      const res = await fetch('/proxy/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chat),
      });
      if (res.ok) {
        setSaveState('saved');
        return true;
      }
      // The proxy answers 5xx when the gateway itself is unreachable.
      setSaveState(res.status >= 500 ? 'offline' : 'failed');
      return false;
    } catch {
      setSaveState('offline');
      return false;
    }
  }, []);

  // Server-confirmed objective from PATCH /chats/{id}/objective — keyed by
  // chat id so a response landing after a thread switch still updates the
  // right chat. undefined mirrors how loaded chats represent "no goal".
  const handleObjectiveSaved = useCallback(
    (chatId: string, objective: string | null) => {
      updateChat(chatId, (c) => ({ ...c, objective: objective ?? undefined }));
    },
    [updateChat],
  );

  const handleRetrySave = useCallback(() => {
    const chat = chats.find((c) => c.id === activeChatId);
    if (chat) void persistChat(chat);
  }, [chats, activeChatId, persistChat]);

  /** Stream one assistant reply into `chat` given `history` (ends with a user
   *  message). Shared by send and retry so the cat's outcome states stay honest. */
  const runStream = useCallback(async (chat: Chat, history: Message[], title: string, attachmentIds: string[] = [], modelOverride?: Model) => {
    const latestUserMessage = [...history].reverse().find((message) => message.role === 'user');
    if (!latestUserMessage) {
      throw new Error('Cannot start a chat turn without a user message');
    }
    // CR-07: a one-shot override applies to this turn only; the next message
    // reverts to normal routing via activeModel.
    const turnModel = modelOverride ?? activeModel;
    setIsStreaming(true);
    setLastOutcome(null);

    const aiMsgId = newMsgId();
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      model: turnModel.name,
    };

    updateChat(chat.id, (c) => ({ ...c, messages: [...history, aiMsg] }));

    const abort = new AbortController();
    abortRef.current = abort;

    let accumulated = '';
    let memoryItems: MemoryEvidence[] | undefined;
    let toolCalls: import('@/lib/types').ToolCall[] | undefined;
    try {
      for await (const chunk of streamChat(
        turnModel.id,
        history,
        abort.signal,
        activeProject?.id,
        chat.id,
        latestUserMessage.id,
        title,
        attachmentIds,
      )) {
        if (chunk.done) break;
        if (chunk.memoryItems?.length) {
          memoryItems = chunk.memoryItems;
          continue;
        }
        if (chunk.toolCalls?.length) {
          toolCalls = chunk.toolCalls;
          updateChat(chat.id, (c) => ({
            ...c,
            messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, toolCalls } : m)),
          }));
          continue;
        }
        accumulated += chunk.content;
        const content = accumulated;
        updateChat(chat.id, (c) => ({
          ...c,
          messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, content } : m)),
        }));
      }

      const mood = inferMood(accumulated, 'assistant');
      const extras = {
        ...(memoryItems ? { memoryItems } : {}),
        ...(toolCalls?.length ? { toolCalls } : {}),
      };
      updateChat(chat.id, (c) => ({
        ...c,
        updatedAt: new Date(),
        messages: c.messages.map((m) =>
          m.id === aiMsgId
            ? { ...m, content: accumulated, mood, ...extras }
            : m,
        ),
      }));
      setLastOutcome('done');
      window.setTimeout(() => setLastOutcome((o) => (o === 'done' ? null : o)), 2500);

      void persistChat({
        id: chat.id,
        title,
        model: turnModel.id,
        color: chat.color,
        createdAt: chat.createdAt,
        updatedAt: new Date(),
        messages: [
          ...history,
          { ...aiMsg, content: accumulated, mood, ...extras },
        ],
      });
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        const interruptedContent = accumulated
          ? `${accumulated}\n\n⚠ generation stopped before completion.`
          : '⚠ generation stopped before Kitty returned a response.';
        const interruptedMessage: Message = {
          ...aiMsg,
          content: interruptedContent,
          mood: 'confused',
          turnStatus: 'interrupted',
        };
        updateChat(chat.id, (c) => ({
          ...c,
          updatedAt: new Date(),
          messages: c.messages.map((m) => (m.id === aiMsgId ? interruptedMessage : m)),
        }));
        void persistChat({
          id: chat.id,
          title,
          model: turnModel.id,
          color: chat.color,
          createdAt: chat.createdAt,
          updatedAt: new Date(),
          messages: [...history, interruptedMessage],
        });
        return;
      }
      setLastOutcome('broke');
      updateChat(chat.id, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === aiMsgId
            ? {
                ...m,
                content: `⚠ ${err instanceof Error ? err.message : 'error connecting to gateway'}`,
                mood: 'confused' as const,
              }
            : m,
        ),
      }));
      // The stream died, but the user's message still deserves to survive a
      // restart — persist it (the ⚠ bubble stays UI-only) and show the outcome.
      void persistChat({
        id: chat.id,
        title,
        model: turnModel.id,
        color: chat.color,
        createdAt: chat.createdAt,
        updatedAt: new Date(),
        messages: history,
      });
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [activeModel, activeProject?.id, updateChat, persistChat]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming || !activeChat) return;

    const userMsg: Message = {
      id: newMsgId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
      attachments: attachments.length ? [...attachments] : undefined,
    };

    // derive title from first message
    const isFirst = activeChat.messages.length === 0;
    const title = isFirst ? text.slice(0, 32) + (text.length > 32 ? '…' : '') : activeChat.title;

    updateChat(activeChat.id, (c) => ({
      ...c,
      title,
      messages: [...c.messages, userMsg],
      updatedAt: new Date(),
    }));
    setInput('');
    setAttachments([]);
    setActiveView('chat');
    const attachmentIds = attachments.map((a) => a.id);
    const oneShot = overrideModel ?? undefined;
    setOverrideModel(null);
    void runStream(activeChat, [...activeChat.messages, userMsg], title, attachmentIds, oneShot);
  }, [input, isStreaming, activeChat, runStream, overrideModel]);


  const handleRetry = useCallback(() => {
    if (!activeChat || isStreaming) return;
    const history = [...activeChat.messages];
    while (history.length && history.at(-1)?.role === 'assistant') history.pop();
    if (history.length === 0) return;
    updateChat(activeChat.id, (c) => ({ ...c, messages: history }));
    void runStream(activeChat, history, activeChat.title);
  }, [activeChat, isStreaming, updateChat, runStream]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleRuntimeSend = useCallback((text: string) => {
    if (!text.trim() || isStreaming || !activeChat) return;
    const userMsg: Message = {
      id: newMsgId(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };
    const isFirst = activeChat.messages.length === 0;
    const title = isFirst ? text.slice(0, 32) + (text.length > 32 ? '…' : '') : activeChat.title;
    updateChat(activeChat.id, (c) => ({
      ...c,
      title,
      messages: [...c.messages, userMsg],
      updatedAt: new Date(),
    }));
    setInput('');
    setAttachments([]);
    setActiveView('chat');
    void runStream(activeChat, [...activeChat.messages, userMsg], title);
  }, [isStreaming, activeChat, updateChat, runStream]);

  const handlePromptSelect = useCallback((text: string) => {
    setInput(text);
    setActiveView('chat');
    setTimeout(() => textareaRef.current?.focus(), 0);
  }, []);

  const [attachmentErrors, setAttachmentErrors] = useState<AttachmentError[]>([]);

  const handleAddFiles = useCallback(
    async (files: FileList) => {
      if (!activeChat) return;
      const { valid, errors } = validateAttachments(files);
      if (errors.length) setAttachmentErrors(errors);
      else setAttachmentErrors([]);

      const added: MessageAttachment[] = [];
      for (const file of valid) {
        const result = await uploadCaptureFile(file, {
          conversationId: activeChat.id,
          projectId: activeProject?.id,
        });
        if (result?.artifact_id) {
          added.push({
            id: result.artifact_id,
            display_name: file.name,
            media_type: file.type || 'application/octet-stream',
            size: file.size,
          });
        }
      }
      if (added.length) setAttachments((prev) => [...prev, ...added]);
    },
    [activeChat, activeProject?.id],
  );

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const handleDecideInChat = useCallback(
    (entry: GatewayTriageEntry) => {
      handlePromptSelect(`Help me decide what to do with this: ${entry.text ?? `inbox entry ${entry.inbox_id}`}`);
    },
    [handlePromptSelect],
  );

  const handleLoopToggle = useCallback(
    (loopId: string) => {
      toggleLoop.mutate(loopId);
    },
    [toggleLoop],
  );

  const handleInsightDismiss = useCallback(
    (insightId: string) => {
      dismissInsight.mutate(insightId);
    },
    [dismissInsight],
  );

  const handleInsightAction = useCallback((_insightId: string, _actionId: string) => {}, []);

  const retryGatewayBootstrap = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['models'] });
    queryClient.invalidateQueries({ queryKey: ['brief'] });
    queryClient.invalidateQueries({ queryKey: ['state'] });
    queryClient.invalidateQueries({ queryKey: ['actions'] });
    queryClient.invalidateQueries({ queryKey: ['todos'] });
    queryClient.invalidateQueries({ queryKey: ['inbox'] });
    queryClient.invalidateQueries({ queryKey: ['loops'] });
    queryClient.invalidateQueries({ queryKey: ['insights'] });
    queryClient.invalidateQueries({ queryKey: ['prompts'] });
  }, [queryClient]);

  const handlePwaInstall = useCallback(() => {
    void pwaInstall.install().catch((error) => {
      console.error('Kitty install failed:', error);
    });
  }, [pwaInstall]);

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        position: 'relative',
        background: 'var(--bg)',
        color: 'var(--ink)',
        fontFamily: 'var(--font-body)',
      }}
    >
      <WobFilters />
      {showOnboarding && (
        <OnboardingModal
          onComplete={({ theme: selectedTheme }) => {
            setTheme(selectedTheme);
            setPreferredName(window.localStorage.getItem('kitty-preferred-name') ?? '');
            document.documentElement.setAttribute('data-theme', selectedTheme);
            setShowOnboarding(false);
          }}
        />
      )}

      {!isMobile && (
        <Rail
          activeView={activeView}
          onViewChange={setActiveView}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {!isMobile && activeView === 'chat' && (
        <SessionSidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleSidebarNewChat}
          onCloseChat={handleCloseChat}
          collapsed={sidebarCollapsed}
        />
      )}

      {isMobile && mobileSidebarOpen && activeView === 'chat' && (
        <>
          <div
            onClick={() => setMobileSidebarOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0, 0, 0, 0.6)',
              zIndex: 40,
            }}
          />
          <div
            style={{
              position: 'fixed',
              inset: '0 auto 0 0',
              width: 'min(320px, 84vw)',
              height: '100vh',
              zIndex: 50,
              boxShadow: 'var(--shadow)',
            }}
          >
            <SessionSidebar
              chats={chats}
              activeChatId={activeChatId}
              onSelectChat={handleSelectChat}
              onNewChat={handleSidebarNewChat}
              onCloseChat={handleCloseChat}
              collapsed={false}
              width="min(320px, 84vw)"
            />
          </div>
        </>
      )}

      <KittyRuntimeProvider
        messages={activeChat?.messages ?? []}
        isStreaming={isStreaming}
        activeModel={activeModel}
        onSend={handleRuntimeSend}
        onCancel={handleStop}
        onReload={handleRetry}
      >
      <main
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden',
          background: 'var(--bg)',
        }}
      >
        <TopBar
          activeModel={activeModel}
          models={availableModels}
          onSelectModel={handleSelectModel}

          isStreaming={isStreaming}
          modelFromGateway={modelGateway.live}
          activeView={activeView}
          onViewChange={setActiveView}
          kittyMode={kittyMode}
          onKittyModeChange={setKittyMode}
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={handleToggleSidebar}
          isMobile={isMobile}
          catState={catState}
          activeProject={activeProject}
          projects={projects}
          onSelectProject={handleSelectProject}
          projectLoading={projectsQuery.isLoading || activeProjectQuery.isLoading}
          projectBusy={setActiveProject.isPending}
          runtimeState={runtimeQuery.data?.connections.gateway.state ?? 'unknown'}
          runtimeDetail={
            runtimeQuery.data?.connections.gateway.reason
            ?? (runtimeQuery.error instanceof Error ? runtimeQuery.error.message : undefined)
          }
        />

        {activeView === 'chat' && (
          <ThreadGoal
            chat={activeChat}
            compact={isMobile}
            onObjectiveSaved={handleObjectiveSaved}
            onEnsurePersisted={persistChat}
          />
        )}

        {activeView === 'chat' && <SignalFeed compact={isMobile} />}

        <PwaInstallBanner
          state={pwaInstall.state}
          error={pwaInstall.error}
          installing={pwaInstall.installing}
          onInstall={handlePwaInstall}
        />

        {modelGateway.loaded && !modelGateway.live && (
          <div
            role="status"
            style={{
              padding: '4px 16px',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--ink-2)',
              borderBottom: '1px solid var(--line)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexShrink: 0,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: 'var(--c-red)',
                  flexShrink: 0,
                  display: 'inline-block',
                }}
              />
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
                color: 'var(--ink-2)',
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--ink)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--ink-2)';
              }}
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
              color: 'var(--ink-2)',
              background: 'rgba(26, 20, 16, 0.5)',
              borderBottom: '1px solid var(--line)',
              flexShrink: 0,
            }}
          >
            Brief unavailable ({briefGateway.error ?? 'unknown'}). Chat still works.
          </div>
        )}

        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
          }}
        >
          <ErrorBoundary name={activeView}>
            {activeView === 'tasks' ? (
              <div
                style={{
                  flex: 1,
                  padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
                  display: 'grid',
                  gap: 24,
                  alignContent: 'start',
                }}
              >
                <TaskPanel />
                <TodoPanel />
              </div>
            ) : activeView === 'tools' ? (
              <div
                style={{
                  flex: 1,
                  padding: isMobile ? '16px 12px 124px' : '20px 24px 40px',
                  display: 'grid',
                  gridTemplateColumns: `repeat(auto-fit, minmax(${isMobile ? 280 : 340}px, 1fr))`,
                  gap: 20,
                  alignContent: 'start',
                }}
              >
                <ToolCard title="agents">
                  <AgentPanel />
                </ToolCard>
                <ToolCard title="monitors">
                  <MonitorPanel />
                </ToolCard>
                <ToolCard title="image gen">
                  <ImageGenPanel />
                </ToolCard>
                <ToolCard title="tutor">
                  <TutorPanel />
                </ToolCard>
                <LoopWatch loops={loops} onToggle={handleLoopToggle} isLoading={loopsQuery.isLoading} />
                <InsightFeed
                  insights={insights}
                  onDismiss={handleInsightDismiss}
                  onAction={handleInsightAction}
                  isLoading={insightsQuery.isLoading}
                />
                <PromptToolkit
                  templates={promptTemplates}
                  onSelect={(tpl) => handlePromptSelect(tpl.content)}
                  isLoading={promptsQuery.isLoading}
                />
              </div>
            ) : activeView === 'terminal' ? (
              <div
                style={{
                  flex: 1,
                  padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <TerminalStrip title="gateway log" maxLines={100} />
              </div>
            ) : activeView === 'projects' ? (
              <div style={panelPadding(isMobile)}>
                <ProjectsPanel />
              </div>
            ) : activeView === 'docs' ? (
              <div style={panelPadding(isMobile)}>
                <DocumentsPanel />
              </div>
            ) : activeView === 'providers' ? (
              <div style={panelPadding(isMobile)}>
                <ProviderCenter />
              </div>
            ) : activeView === 'agents' ? (
              <div style={panelPadding(isMobile)}>
                <ToolCard title="agents — spawn, watch, stop">
                  <AgentPanel />
                </ToolCard>
              </div>
            ) : activeView === 'images' ? (
              <div style={panelPadding(isMobile)}>
                <ToolCard title="image lab — local pipeline">
                  <ImageGenPanel />
                </ToolCard>
                <p
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    color: 'var(--ink-2)',
                    lineHeight: 1.6,
                  }}
                >
                  runs on the local engine via the gateway. ComfyUI stays an external service —
                  planned, not wired.
                </p>
              </div>
            ) : activeView === 'tutor' ? (
              <div style={panelPadding(isMobile)}>
                <ToolCard title="tutor — learn, quiz, master">
                  <TutorPanel />
                </ToolCard>
              </div>
            ) : activeView === 'settings' ? (
              <div style={panelPadding(isMobile)}>
                <SettingsPanel theme={theme} onToggleTheme={handleToggleTheme} />
              </div>
            ) : activeView === 'builder' ? (
              <div style={panelPadding(isMobile)}>
                <BuilderPanel onBack={() => setActiveView('home')} />
              </div>
            ) : activeView === 'chat' && activeChat && activeChat.messages.length > 0 ? (
              <div
                style={{
                  padding: isMobile ? '18px 14px 16px' : '30px 44px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 18,
                  paddingBottom: isMobile ? 176 : 140,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: 0.7 }}>
                  <span style={{ flex: 1, height: 1.5, background: 'var(--line)' }} />
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 10,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color: 'var(--ink-2)',
                    }}
                  >
                    today
                  </span>
                  <span style={{ flex: 1, height: 1.5, background: 'var(--line)' }} />
                </div>
                {activeChat.messages.map((msg, i) => {
                  const isLast = i === activeChat.messages.length - 1;
                  const prev = i > 0 ? activeChat.messages[i - 1] : null;
                  const isFirstInRun = !prev || prev.role !== msg.role;
                  return (
                    <ChatMessage
                      key={msg.id}
                      message={msg}
                      chatId={activeChat.id}
                      messageIndex={i}
                      isStreaming={isStreaming && isLast && msg.role === 'assistant'}
                      isFirstInRun={isFirstInRun}
                      catState={catState}
                      compact={isMobile}
                      onRetry={isLast && msg.role === 'assistant' && !isStreaming ? handleRetry : undefined}
                    />
                  );
                })}
                <div ref={bottomRef} />
              </div>
            ) : activeView === 'chat' ? (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 30,
                  paddingBottom: 100,
                  maxWidth: 420,
                  margin: '0 auto',
                  textAlign: 'center',
                  padding: 40,
                }}
              >
                <div className="cat-idle" style={{ position: 'relative' }}>
                  <CatBody size={140} />
                </div>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                    alignItems: 'center',
                  }}
                >
                  <h1
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontWeight: 800,
                      fontSize: 64,
                      letterSpacing: '-0.035em',
                      color: 'var(--ink)',
                      lineHeight: 0.86,
                    }}
                  >
                    hey.
                  </h1>
                  <p
                    style={{
                      fontSize: 16,
                      lineHeight: 1.6,
                      color: 'var(--ink-2)',
                      maxWidth: 300,
                    }}
                  >
                    {
                      "i'm kitty. drawn by a six-year-old, allegedly. here when you need me — let's get things done."
                    }
                  </p>
                </div>
                <button
                  onClick={() => {
                    textareaRef.current?.focus();
                  }}
                  style={{
                    background: 'var(--primary)',
                    color: 'var(--on-primary)',
                    border: 'none',
                    borderRadius: 14,
                    padding: '14px 40px',
                    fontFamily: 'var(--font-body)',
                    fontSize: 16,
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: 'var(--btn-shadow)',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {"let's go →"}
                </button>

                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 9,
                    justifyContent: 'center',
                    marginTop: 8,
                  }}
                >
                  {['plan my week', 'draft a reply', "what's on today", 'summarise a doc'].map(
                    (chip) => (
                      <button
                        key={chip}
                        onClick={() => {
                          setInput(chip);
                          textareaRef.current?.focus();
                        }}
                        style={{
                          fontFamily: 'var(--font-body)',
                          fontSize: 13,
                          color: 'var(--ink)',
                          background: 'var(--surface)',
                          border: '1.5px solid var(--line)',
                          borderRadius: 12,
                          padding: '8px 16px',
                          cursor: 'pointer',
                        }}
                      >
                        {chip}
                      </button>
                    ),
                  )}
                </div>
              </div>
            ) : activeView === 'home' ? (
              <HomeState
                compact={isMobile}
                preferredName={preferredName}
                onDecideInChat={handleDecideInChat}
                onNavigate={setActiveView}
              />
            ) : (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--ink-2)',
                  fontSize: 14,
                }}
              >
                <span style={{ fontSize: 32, opacity: 0.3 }}>?</span>
                <span>{activeView} view</span>
                <span style={{ fontSize: 12, color: 'var(--ink-2)' }}>coming soon</span>
              </div>
            )}
          </ErrorBoundary>
        </div>

        {activeView === 'chat' && saveState !== 'idle' && (
          <div
            role="status"
            style={{
              padding: '2px 28px',
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              display: 'flex',
              justifyContent: 'flex-start',
              alignItems: 'center',
              gap: 8,
              flexShrink: 0,
              color:
                saveState === 'saved'
                  ? 'var(--ink-2)'
                  : saveState === 'saving'
                    ? 'var(--ink-2)'
                    : 'var(--c-red)',
            }}
          >
            {saveState === 'saving' && <span>saving…</span>}
            {saveState === 'saved' && <span>saved</span>}
            {saveState === 'failed' && <span>save failed — chat not persisted</span>}
            {saveState === 'offline' && <span>gateway offline — chat not saved</span>}
            {(saveState === 'failed' || saveState === 'offline') && (
              <button
                type="button"
                onClick={handleRetrySave}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  fontWeight: 600,
                  textDecoration: 'underline',
                  color: 'inherit',
                }}
              >
                retry
              </button>
            )}
          </div>
        )}

        {activeView === 'chat' && attachmentErrors.length > 0 && (
          <div
            role="alert"
            style={{
              padding: '4px 28px',
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--c-red)',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              flexShrink: 0,
            }}
          >
            {attachmentErrors.map((err, i) => (
              <span key={i}>{err.file}: {err.reason}</span>
            ))}
          </div>
        )}

        {activeView === 'chat' && <ActiveTaskCards compact={isMobile} />}

        {activeView === 'chat' && (
          <InputBar
            value={input}
            onChange={(v: string) => { setInput(v); if (attachmentErrors.length) setAttachmentErrors([]); }}
            onSend={handleSend}
            onStop={handleStop}
            isStreaming={isStreaming}
            disabled={isStreaming}
            chatTitle={activeChat?.title}
            modelName={activeModel.name}
            modelColor={activeModel.color}
            tokenCount={tokenCount}
            maxTokens={200000}
            textareaRef={textareaRef}
            compact={isMobile}
            attachments={attachments}
            onAddFiles={handleAddFiles}
            onRemoveAttachment={handleRemoveAttachment}
            models={availableModels}
            overrideModel={overrideModel}
            onOverrideModel={setOverrideModel}
          />
        )}
      </main>
      </KittyRuntimeProvider>

      <CatCorner state={catState} />
      <PaperGrain />

      <CommandPalette
        chats={chats}
        onNewChat={handleSidebarNewChat}
        onSelectChat={handleSelectChat}
        onViewChange={setActiveView}
        onToggleSidebar={handleToggleSidebar}
      />
    </div>
  );
}
