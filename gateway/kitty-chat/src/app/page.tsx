'use client';
import { startTransition, useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Chat, Message, Model, MODELS, COLOR_CYCLE, ChatColor } from '@/lib/types';
import { streamChat } from '@/lib/chat-client';
import { inferMood } from '@/lib/mood';
import { TopBar } from '@/components/TopBar';
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
import { LoopWatch } from '@/components/LoopWatch';
import { InsightFeed } from '@/components/InsightFeed';
import { PromptToolkit } from '@/components/PromptToolkit';
import { CommandPalette } from '@/components/CommandPalette';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { PwaInstallBanner } from '@/components/PwaInstallBanner';
import { WobFilters, PaperGrain } from '@/components/WobFilters';
import { CatCorner, CatBody, type CatState } from '@/components/CrayonCat';
import { fetchGatewaySearch, type GatewaySearchSnapshot, type GatewayTriageEntry } from '@/lib/gateway';
import { usePwaInstall } from '@/lib/pwa';
import {
  useGatewayBrief,
  useGatewayModels,
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
  const [showModelMenu, setShowModelMenu] = useState(false);
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
  const [theme, setTheme] = useState<'day' | 'night'>('day');
  const pwaInstall = usePwaInstall();

  const catState: CatState = isStreaming ? 'working' : 'idle';

  useEffect(() => {
    fetch('/proxy/chats')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const saved: Chat[] = d?.chats ?? [];
        if (saved.length) {
          setChats(
            saved.map((c: Chat) => ({
              ...c,
              createdAt: new Date(c.createdAt),
              updatedAt: new Date(c.updatedAt),
              messages: (c.messages ?? []).map((m: Message) => ({
                ...m,
                timestamp: new Date(m.timestamp),
              })),
            })),
          );
        }
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

  // Gateway status queries — models for TopBar, brief for the offline banner.
  const queryClient = useQueryClient();
  const modelsQuery = useGatewayModels();
  const briefQuery = useGatewayBrief();
  // Loops/insights/prompts still bind to real data but aren't part of the
  // console home surface — they live in the Tools view instead.
  const loopsQuery = useLoops();
  const insightsQuery = useInsights();
  const promptsQuery = usePrompts();
  const toggleLoop = useToggleLoop();
  const dismissInsight = useDismissInsight();

  const availableModels = modelsQuery.data?.models ?? MODELS;
  const modelGateway = {
    loaded: modelsQuery.isFetched,
    live: modelsQuery.data?.fromLiveGateway ?? true,
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

  // Sync activeModel with the models list once it loads (or after retry).
  useEffect(() => {
    if (!modelsQuery.data) return;
    const models = modelsQuery.data.models;
    setActiveModel((current) => models.find((m) => m.id === current.id) ?? models[0] ?? current);
  }, [modelsQuery.data]);

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
      const next = t === 'day' ? 'night' : 'day';
      document.documentElement.setAttribute('data-theme', next);
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

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming || !activeChat) return;

    const userMsg: Message = {
      id: newMsgId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
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
    setActiveView('chat');
    setIsStreaming(true);

    const aiMsgId = newMsgId();
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      model: activeModel.name,
    };

    updateChat(activeChat.id, (c) => ({ ...c, messages: [...c.messages, aiMsg] }));

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const history = [...activeChat.messages, userMsg];
      let accumulated = '';

      for await (const chunk of streamChat(activeModel.id, history, abort.signal)) {
        if (chunk.done) break;
        accumulated += chunk.content;
        const content = accumulated;
        updateChat(activeChat.id, (c) => ({
          ...c,
          messages: c.messages.map((m) => (m.id === aiMsgId ? { ...m, content } : m)),
        }));
      }

      const mood = inferMood(accumulated, 'assistant');
      updateChat(activeChat.id, (c) => ({
        ...c,
        updatedAt: new Date(),
        messages: c.messages.map((m) =>
          m.id === aiMsgId ? { ...m, content: accumulated, mood } : m,
        ),
      }));

      // Persist to SQLite — fire and forget, React state is the source of truth
      fetch('/proxy/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: activeChat.id,
          title,
          model: activeModel.id,
          color: activeChat.color,
          createdAt: activeChat.createdAt,
          updatedAt: new Date(),
          messages: [...activeChat.messages, userMsg, { ...aiMsg, content: accumulated, mood }],
        }),
      }).catch(() => {});
    } catch (err: unknown) {
      // User pressed Stop — keep whatever streamed so far, don't show an error.
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      updateChat(activeChat.id, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === aiMsgId
            ? {
                ...m,
                content: `⚠ ${err instanceof Error ? err.message : 'Error connecting to gateway'}`,
                mood: 'confused' as const,
              }
            : m,
        ),
      }));
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [input, isStreaming, activeChat, activeModel, updateChat]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handlePromptSelect = useCallback((text: string) => {
    setInput(text);
    setActiveView('chat');
    setTimeout(() => textareaRef.current?.focus(), 0);
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
      onClick={() => showModelMenu && setShowModelMenu(false)}
    >
      <WobFilters />

      {!isMobile && (
        <Rail
          activeView={activeView}
          onViewChange={setActiveView}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      )}

      {!isMobile && (
        <SessionSidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleSidebarNewChat}
          onCloseChat={handleCloseChat}
          collapsed={sidebarCollapsed}
        />
      )}

      {isMobile && mobileSidebarOpen && (
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
          onToggleSidebar={handleToggleSidebar}
          isMobile={isMobile}
          catState={catState}
        />

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
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: 'var(--error)',
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
                color: 'var(--text-muted)',
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--text)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)';
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
              color: 'var(--text-dim)',
              background: 'rgba(26, 20, 16, 0.5)',
              borderBottom: '1px solid var(--border)',
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
                <ToolCard title="Agents">
                  <AgentPanel />
                </ToolCard>
                <ToolCard title="Monitors">
                  <MonitorPanel />
                </ToolCard>
                <ToolCard title="Image gen">
                  <ImageGenPanel />
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
                <TerminalStrip title="Gateway Log" maxLines={100} />
              </div>
            ) : activeView === 'chat' && activeChat && activeChat.messages.length > 0 ? (
              <div
                style={{
                  padding: '30px 44px 16px',
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
                      isStreaming={isStreaming && isLast && msg.role === 'assistant'}
                      isFirstInRun={isFirstInRun}
                      catState={catState}
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
                gatewayError={!briefGateway.live ? briefGateway.error : null}
                onDecideInChat={handleDecideInChat}
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
                  color: 'var(--text-muted)',
                  fontSize: 14,
                }}
              >
                <span style={{ fontSize: 32, opacity: 0.3 }}>?</span>
                <span>{activeView} view</span>
                <span style={{ fontSize: 12, color: 'var(--text-ghost)' }}>coming soon</span>
              </div>
            )}
          </ErrorBoundary>
        </div>

        {activeView === 'chat' && (
          <InputBar
            value={input}
            onChange={setInput}
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
          />
        )}
      </main>

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
