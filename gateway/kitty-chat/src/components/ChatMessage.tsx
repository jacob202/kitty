'use client'
import { isValidElement, useRef, useState, type ReactNode, type CSSProperties } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Copy, Check, RotateCcw, Paperclip, ThumbsUp, ThumbsDown } from 'lucide-react'
import { Message, type MemoryEvidence } from '@/lib/types'
import { deleteMemory } from '@/lib/gateway'
import { useSubmitMessageFeedback, type MessageFeedbackRating } from '@/lib/queries'
import { CatFaceBadge, type CatState } from './CrayonCat'
import { ToolCallList } from './ToolCallBlock'

interface Props {
  message: Message
  isStreaming?: boolean
  isFirstInRun?: boolean
  catState?: CatState
  onRetry?: () => void
  chatId: string
  messageIndex: number
  /** Phone layout: reveal hover-only actions and size targets for touch. */
  compact?: boolean
}

export function ChatMessage({ message, isStreaming, catState = 'idle', onRetry, chatId, messageIndex, compact = false }: Props) {
  const isUser = message.role === 'user'
  const isKitty = !isUser
  const attachments = message.attachments ?? []
  const turnStatus = message.turnStatus
  const showTurnStatus =
    isKitty && turnStatus !== undefined && turnStatus !== 'succeeded'
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [copied, setCopied] = useState(false)
  const feedback = useSubmitMessageFeedback()

  const copyMessage = () => {
    if (!message.content) return
    void navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    })
  }

  const showActions = isKitty && !isStreaming && Boolean(message.content)
  // On touch (compact) there is no hover to reveal actions — keep them visible.
  const actionsVisible = hovered || focused || compact

  const submitFeedback = (rating: MessageFeedbackRating) => {
    feedback.mutate({ chatId, messageIndex, rating })
  }

  return (
    <div className="msg-in" style={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: 10,
      flexDirection: isKitty ? 'row' : 'row-reverse',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false)
      }}
    >
      {isKitty && <CatFaceBadge state={catState} />}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: isKitty ? 'flex-start' : 'flex-end' }}>
          {attachments.length > 0 && (
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              marginBottom: 2,
              justifyContent: isKitty ? 'flex-start' : 'flex-end',
            }}>
              {attachments.map((att) => (
                <span key={att.id} style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  background: isKitty ? 'var(--surface-2)' : 'rgba(255,255,255,0.18)',
                  border: isKitty ? '1.5px solid var(--line)' : 'none',
                  borderRadius: 8,
                  padding: '3px 8px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10.5,
                  color: isKitty ? 'var(--ink-2)' : 'var(--on-primary)',
                }}>
                  <Paperclip size={10} />
                  {att.display_name}
                </span>
              ))}
            </div>
          )}
          <div style={{
            maxWidth: 560,
            borderRadius: isKitty ? '5px 17px 17px 17px' : '17px 5px 17px 17px',
            padding: '11px 16px',
            background: isKitty ? 'var(--surface)' : 'var(--primary)',
            border: isKitty ? '1.5px solid var(--line)' : 'none',
            boxShadow: 'var(--shadow-soft)',
          }}>
            {isStreaming && !message.content && !message.toolCalls?.length ? (
              <TypingDots />
            ) : (
              <>
                <MessageContent content={message.content} isUser={isUser} />
                {message.toolCalls && message.toolCalls.length > 0 && (
                  <ToolCallList toolCalls={message.toolCalls} isStreaming={isStreaming} />
                )}
              </>
            )}
          </div>
        {isKitty && !isStreaming && message.memoryItems && message.memoryItems.length > 0 && (
          <MemoryBlock items={message.memoryItems} />
        )}
        {showActions && (
          <div className="msg-actions" style={{ ...actionRowStyle, opacity: actionsVisible ? 1 : 0 }}>
            <button onClick={copyMessage} style={actionBtnStyle} title="copy message">
              {copied ? <Check size={10} /> : <Copy size={10} />}
              <span>{copied ? 'copied' : 'copy'}</span>
            </button>
            {onRetry && (
              <button onClick={onRetry} style={actionBtnStyle} title="regenerate this reply">
                <RotateCcw size={10} />
                <span>retry</span>
              </button>
            )}
            <button
              onClick={() => submitFeedback('up')}
              style={actionBtnStyle}
              title="rate this response helpful"
              aria-label="rate this response helpful"
              disabled={feedback.isPending}
            >
              <ThumbsUp size={11} />
            </button>
            <button
              onClick={() => submitFeedback('down')}
              style={actionBtnStyle}
              title="rate this response unhelpful"
              aria-label="rate this response unhelpful"
              disabled={feedback.isPending}
            >
              <ThumbsDown size={11} />
            </button>
          </div>
        )}
        {feedback.isPending && (
          <div style={actionRowStyle} aria-live="polite">
            <span style={{ fontSize: 10 }}>saving feedback…</span>
          </div>
        )}
        {feedback.isError && (
          <div style={{ ...actionRowStyle, color: 'var(--c-red)' }} role="alert">
            <span style={{ fontSize: 10 }}>feedback failed: {feedback.error.message}</span>
          </div>
        )}
        {showTurnStatus && (
          <div style={{
            ...actionRowStyle,
            color: turnStatus === 'failed' ? 'var(--c-red)' : 'var(--ink-2)',
          }}>
            <span style={{ fontSize: 10 }}>{turnStatus}</span>
          </div>
        )}
        {showActions && (message.model || message.routing?.length) && (
          <Attribution message={message} />
        )}
      </div>
    </div>
  )
}

function MessageContent({ content, isUser }: { content: string; isUser: boolean }) {
  return (
    <div style={{
      ...bodyStyle,
      color: isUser ? 'var(--on-primary)' : 'var(--ink)',
    }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          p: ({ children }) => <p style={pStyle}>{children}</p>,
          h1: ({ children }) => <h1 style={h1Style}>{children}</h1>,
          h2: ({ children }) => <h2 style={h2Style}>{children}</h2>,
          h3: ({ children }) => <h3 style={h3Style}>{children}</h3>,
          ul: ({ children }) => <ul style={ulStyle}>{children}</ul>,
          ol: ({ children }) => <ol style={olStyle}>{children}</ol>,
          li: ({ children }) => <li style={liStyle}>{children}</li>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer" style={linkStyle}>{children}</a>
          ),
          blockquote: ({ children }) => <blockquote style={quoteStyle}>{children}</blockquote>,
          hr: () => <hr style={hrStyle} />,
          table: ({ children }) => (
            <div style={tableWrapStyle}><table style={tableStyle}>{children}</table></div>
          ),
          th: ({ children }) => <th style={thStyle}>{children}</th>,
          td: ({ children }) => <td style={tdStyle}>{children}</td>,
          pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
          code: ({ className, children, ...props }) => {
            const isBlock = typeof className === 'string' && className.startsWith('language-')
            if (isBlock) {
              return <code className={className} style={blockCodeStyle} {...props}>{children}</code>
            }
            return <code style={inlineCodeStyle} {...props}>{children}</code>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function CodeBlock({ children }: { children: ReactNode }) {
  const [copied, setCopied] = useState(false)
  const preRef = useRef<HTMLPreElement>(null)

  let lang = ''
  if (isValidElement<{ className?: string }>(children)) {
    const cls = children.props.className ?? ''
    const m = cls.match(/language-(\w+)/)
    if (m) lang = m[1]
  }

  const copy = () => {
    const text = preRef.current?.innerText ?? ''
    if (!text) return
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div style={codeBoxStyle}>
      <div style={codeBoxHeaderStyle}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', letterSpacing: '0.05em' }}>
          {lang || 'code'}
        </span>
        <button onClick={copy} style={copyBtnStyle} title="copy">
          {copied ? <Check size={11} /> : <Copy size={11} />}
          <span>{copied ? 'copied' : 'copy'}</span>
        </button>
      </div>
      <pre ref={preRef} style={preStyle}>{children}</pre>
    </div>
  )
}

function Attribution({ message }: { message: Message }) {
  const routing = message.routing ?? []
  const agentLabel = message.model ?? (routing[0]?.agent ?? 'kitty')
  return (
    <div style={{ ...actionRowStyle, flexWrap: 'wrap', gap: 6 }}>
      <span style={{ fontSize: 10, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)' }}>
        answered by {agentLabel}
      </span>
      {routing.map((r) => (
        <span
          key={r.task_id}
          title={`${r.category} · priority ${r.priority}`}
          style={{
            fontSize: 9.5,
            color: 'var(--ink-2)',
            border: '1px solid var(--line)',
            borderRadius: 999,
            padding: '1px 7px',
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'nowrap',
          }}
        >
          {r.agent} · p{r.priority}
        </span>
      ))}
    </div>
  )
}

/** How long a "forget" stays cancellable before the DELETE fires (CR-06).
 *  Destructive + phone-first: a single tap must never delete. */
export const FORGET_GRACE_MS = 5000

type ForgetState = 'idle' | 'pending' | 'deleting' | 'forgotten' | 'error'

/** One memory row: text + (when deletable) a forget flow with undo grace. */
function MemoryRow({ item }: { item: MemoryEvidence }) {
  const [state, setState] = useState<ForgetState>('idle')
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<number | null>(null)

  const fire = async (memoryId: string) => {
    setState('deleting')
    try {
      await deleteMemory(memoryId)
      setState('forgotten')
    } catch (err) {
      setState('error')
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const arm = () => {
    if (!item.memoryId) return
    const memoryId = item.memoryId
    setState('pending')
    setError(null)
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null
      void fire(memoryId)
    }, FORGET_GRACE_MS)
  }

  const undo = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setState('idle')
    setError(null)
  }

  // ponytail: no unmount cleanup for the timer — firing after unmount still
  // performs exactly the confirmed delete; only the label update is lost.

  if (state === 'forgotten') {
    return (
      <li style={{ ...memoryItemStyle, opacity: 0.55 }}>
        <s>{item.text}</s>
        <span style={forgetHintStyle}> · forgotten</span>
      </li>
    )
  }

  return (
    <li style={memoryItemStyle}>
      {state === 'pending' ? <s>{item.text}</s> : item.text}
      {item.memoryId && state === 'idle' && (
        <button onClick={arm} aria-label={`Forget memory: ${item.text}`} style={forgetBtnStyle}>
          forget
        </button>
      )}
      {state === 'pending' && (
        <button
          onClick={undo}
          aria-label={`Undo forgetting: ${item.text}`}
          style={{ ...forgetBtnStyle, color: 'var(--c-red)', fontWeight: 700 }}
        >
          undo
        </button>
      )}
      {state === 'deleting' && <span style={forgetHintStyle}> forgetting…</span>}
      {state === 'error' && (
        <span role="alert" style={{ ...forgetHintStyle, color: 'var(--c-red)' }}>
          {' '}not forgotten — {error}
        </span>
      )}
    </li>
  )
}

/** Collapsed list of the memories that informed a reply (CR-05), with inline
 *  forget-with-undo correction (CR-06). */
function MemoryBlock({ items }: { items: MemoryEvidence[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ paddingLeft: 6, maxWidth: 560 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={memoryToggleStyle}
      >
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>
        kitty remembered {items.length === 1 ? '1 thing' : `${items.length} things`}…
      </button>
      {open && (
        <ul style={memoryListStyle}>
          {items.map((item, i) => (
            <MemoryRow key={item.memoryId ?? `text-${i}`} item={item} />
          ))}
        </ul>
      )}
    </div>
  )
}

function TypingDots() {
  return (
    <span style={{ display: 'flex', gap: 5, alignItems: 'center', height: 16 }}>
      <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink-2)', animation: 'dot1 1.2s ease-in-out infinite' }} />
      <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink-2)', animation: 'dot2 1.2s ease-in-out infinite' }} />
      <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink-2)', animation: 'dot3 1.2s ease-in-out infinite' }} />
    </span>
  )
}

const memoryToggleStyle: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  minHeight: 32, background: 'transparent', border: 'none',
  padding: '2px 4px', color: 'var(--ink-2)',
  fontFamily: 'var(--font-mono)', fontSize: 10,
  cursor: 'pointer', borderRadius: 4,
}
const memoryListStyle: CSSProperties = {
  margin: '2px 0 4px', padding: '8px 12px 8px 26px',
  listStyle: 'disc', background: 'var(--surface-2)',
  border: '1px solid var(--line)', borderRadius: 8,
  display: 'flex', flexDirection: 'column', gap: 4,
}
const memoryItemStyle: CSSProperties = {
  fontFamily: 'var(--font-body)', fontSize: 12,
  lineHeight: 1.45, color: 'var(--ink-2)', wordBreak: 'break-word',
}
const forgetBtnStyle: CSSProperties = {
  marginLeft: 8, padding: '2px 8px', minHeight: 24,
  fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)',
  background: 'transparent', border: '1px solid var(--line)',
  borderRadius: 6, cursor: 'pointer', verticalAlign: 'middle',
}
const forgetHintStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)',
}

const actionRowStyle: CSSProperties = {
  display: 'flex', gap: 10, paddingLeft: 6,
  transition: 'opacity 0.12s linear',
}
const actionBtnStyle: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  minWidth: 44, minHeight: 44, justifyContent: 'center',
  background: 'transparent', border: 'none', padding: '2px 4px',
  color: 'var(--ink-2)', fontFamily: 'var(--font-mono)',
  fontSize: 10, cursor: 'pointer', borderRadius: 4,
}

const bodyStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 14.5,
  lineHeight: 1.5,
  wordBreak: 'break-word',
}
const pStyle: CSSProperties = { margin: '0 0 8px' }
const h1Style: CSSProperties = { fontSize: 18, fontWeight: 700, margin: '14px 0 8px' }
const h2Style: CSSProperties = { fontSize: 16, fontWeight: 700, margin: '14px 0 8px' }
const h3Style: CSSProperties = { fontSize: 14.5, fontWeight: 700, margin: '12px 0 6px' }
const ulStyle: CSSProperties = { margin: '0 0 10px', paddingLeft: 22 }
const olStyle: CSSProperties = { margin: '0 0 10px', paddingLeft: 22 }
const liStyle: CSSProperties = { margin: '2px 0' }
const linkStyle: CSSProperties = { color: 'var(--primary)', textDecoration: 'underline', textUnderlineOffset: 2 }
const quoteStyle: CSSProperties = {
  margin: '8px 0', padding: '6px 12px',
  borderLeft: '3px solid var(--line)', color: 'var(--ink-2)',
  background: 'var(--surface-2)', borderRadius: '0 6px 6px 0',
}
const hrStyle: CSSProperties = { border: 0, borderTop: '1px solid var(--line)', margin: '12px 0' }
const tableWrapStyle: CSSProperties = {
  margin: '8px 0 12px', overflowX: 'auto',
  border: '1.5px solid var(--line)', borderRadius: 8,
}
const tableStyle: CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: 13 }
const thStyle: CSSProperties = {
  textAlign: 'left', padding: '6px 10px',
  background: 'var(--surface-2)', borderBottom: '1px solid var(--line)',
  fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
  letterSpacing: '0.03em', color: 'var(--ink)',
}
const tdStyle: CSSProperties = {
  padding: '6px 10px', borderTop: '1px solid var(--line)', color: 'var(--ink-2)',
}
const codeBoxStyle: CSSProperties = {
  margin: '8px 0 12px', background: 'var(--surface-2)',
  border: '1.5px solid var(--line)', borderRadius: 8, overflow: 'hidden',
}
const codeBoxHeaderStyle: CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '4px 10px', background: 'var(--surface-2)',
  borderBottom: '1px solid var(--line)',
}
const copyBtnStyle: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  background: 'transparent', border: 'none', padding: '2px 4px',
  color: 'var(--ink-2)', fontFamily: 'var(--font-mono)',
  fontSize: 10, cursor: 'pointer', borderRadius: 4,
}
const preStyle: CSSProperties = {
  margin: 0, padding: '12px 14px', overflowX: 'auto',
  fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 1.5,
}
const blockCodeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 13,
  color: 'var(--ink)', background: 'transparent',
}
const inlineCodeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 12,
  padding: '1px 6px', borderRadius: 4,
  background: 'var(--surface-2)', border: '1px solid var(--line)',
  color: 'var(--primary)',
}
