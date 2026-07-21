'use client'

import { createContext, useContext, useCallback, type CSSProperties } from 'react'
import { ThreadPrimitive } from '@assistant-ui/react'
import type { Message } from '@/lib/types'
import { ChatMessage } from './ChatMessage'
import { CatBody, type CatState } from './CrayonCat'

interface KittyThreadContextValue {
  messages: Message[]
  chatId: string
  isStreaming: boolean
  catState: CatState
  compact: boolean
  onRetry?: () => void
}

const KittyThreadContext = createContext<KittyThreadContextValue>({
  messages: [],
  chatId: '',
  isStreaming: false,
  catState: 'idle',
  compact: false,
})

interface KittyThreadProps {
  messages: Message[]
  chatId: string
  isStreaming: boolean
  catState: CatState
  compact: boolean
  onRetry?: () => void
  onChipClick?: (text: string) => void
  onStartClick?: () => void
}

export function KittyThread({
  messages,
  chatId,
  isStreaming,
  catState,
  compact,
  onRetry,
  onChipClick,
  onStartClick,
}: KittyThreadProps) {
  const ctx: KittyThreadContextValue = {
    messages,
    chatId,
    isStreaming,
    catState,
    compact,
    onRetry,
  }

  return (
    <KittyThreadContext.Provider value={ctx}>
      <ThreadPrimitive.Root style={rootStyle}>
        <ThreadPrimitive.Viewport autoScroll style={viewportStyle(compact)}>
          <ThreadPrimitive.Empty>
            <EmptyState
              compact={compact}
              onStartClick={onStartClick}
              onChipClick={onChipClick}
            />
          </ThreadPrimitive.Empty>

          <MessageList />

          <ThreadPrimitive.ViewportFooter style={footerStyle}>
            <ThreadPrimitive.ScrollToBottom style={scrollBtnStyle}>
              <span style={scrollBtnArrow}>↓</span>
            </ThreadPrimitive.ScrollToBottom>
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </KittyThreadContext.Provider>
  )
}

function MessageList() {
  const ctx = useContext(KittyThreadContext)

  const renderMessage = useCallback(
    ({ message }: { message: { id: string; index: number; isLast: boolean; role: string } }) => {
      const rawMsg = ctx.messages[message.index]
      if (!rawMsg) return null

      const prev = message.index > 0 ? ctx.messages[message.index - 1] : null
      const isFirstInRun = !prev || prev.role !== rawMsg.role

      return (
        <>
          {message.index === 0 && <TodayDivider />}
          <ChatMessage
            message={rawMsg}
            chatId={ctx.chatId}
            messageIndex={message.index}
            isStreaming={ctx.isStreaming && message.isLast && rawMsg.role === 'assistant'}
            isFirstInRun={isFirstInRun}
            catState={ctx.catState}
            compact={ctx.compact}
            onRetry={
              message.isLast && rawMsg.role === 'assistant' && !ctx.isStreaming
                ? ctx.onRetry
                : undefined
            }
          />
        </>
      )
    },
    [ctx],
  )

  return <ThreadPrimitive.Messages>{renderMessage}</ThreadPrimitive.Messages>
}

function TodayDivider() {
  return (
    <div style={dividerStyle}>
      <span style={dividerLine} />
      <span style={dividerLabel}>today</span>
      <span style={dividerLine} />
    </div>
  )
}

function EmptyState({
  compact,
  onStartClick,
  onChipClick,
}: {
  compact: boolean
  onStartClick?: () => void
  onChipClick?: (text: string) => void
}) {
  return (
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
        <h1 style={heroStyle}>hey.</h1>
        <p style={{ fontSize: 16, lineHeight: 1.6, color: 'var(--ink-2)', maxWidth: 300 }}>
          {"i'm kitty. drawn by a six-year-old, allegedly. here when you need me — let's get things done."}
        </p>
      </div>
      <button onClick={onStartClick} style={startBtnStyle}>
        {"let's go →"}
      </button>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, justifyContent: 'center', marginTop: 8 }}>
        {SUGGESTION_CHIPS.map((chip) => (
          <button key={chip} onClick={() => onChipClick?.(chip)} style={chipStyle}>
            {chip}
          </button>
        ))}
      </div>
    </div>
  )
}

const SUGGESTION_CHIPS = ['plan my week', 'draft a reply', "what's on today", 'summarise a doc']

const rootStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
  overflow: 'hidden',
}

function viewportStyle(compact: boolean): CSSProperties {
  return {
    flex: 1,
    overflowY: 'auto',
    minHeight: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 18,
    padding: compact ? '18px 14px 16px' : '30px 44px 16px',
    paddingBottom: compact ? 176 : 140,
  }
}

const footerStyle: CSSProperties = {
  position: 'sticky',
  bottom: 0,
  display: 'flex',
  justifyContent: 'center',
  pointerEvents: 'none',
  padding: '0 0 8px',
}

const scrollBtnStyle: CSSProperties = {
  pointerEvents: 'auto',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 32,
  height: 32,
  borderRadius: 99,
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
  cursor: 'pointer',
  color: 'var(--ink-2)',
}

const scrollBtnArrow: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 14,
  fontWeight: 700,
  lineHeight: 1,
}

const dividerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  opacity: 0.7,
}

const dividerLine: CSSProperties = {
  flex: 1,
  height: 1.5,
  background: 'var(--line)',
}

const dividerLabel: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  color: 'var(--ink-2)',
}

const heroStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 800,
  fontSize: 64,
  letterSpacing: '-0.035em',
  color: 'var(--ink)',
  lineHeight: 0.86,
}

const startBtnStyle: CSSProperties = {
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
}

const chipStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--ink)',
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  borderRadius: 12,
  padding: '8px 16px',
  cursor: 'pointer',
}
