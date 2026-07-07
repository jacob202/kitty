'use client'
import { isValidElement, useRef, useState, type ReactNode, type CSSProperties } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Copy, Check, RotateCcw } from 'lucide-react'
import { Message } from '@/lib/types'
import { CatFaceBadge, type CatState } from './CrayonCat'

interface Props {
  message: Message
  isStreaming?: boolean
  isFirstInRun?: boolean
  catState?: CatState
  onRetry?: () => void
}

export function ChatMessage({ message, isStreaming, catState = 'idle', onRetry }: Props) {
  const isUser = message.role === 'user'
  const isKitty = !isUser
  const [hovered, setHovered] = useState(false)
  const [copied, setCopied] = useState(false)

  const copyMessage = () => {
    if (!message.content) return
    void navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    })
  }

  const showActions = isKitty && !isStreaming && Boolean(message.content)

  return (
    <div className="msg-in" style={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: 10,
      flexDirection: isKitty ? 'row' : 'row-reverse',
    }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {isKitty && <CatFaceBadge state={catState} />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: isKitty ? 'flex-start' : 'flex-end' }}>
        <div style={{
          maxWidth: 560,
          borderRadius: isKitty ? '5px 17px 17px 17px' : '17px 5px 17px 17px',
          padding: '11px 16px',
          background: isKitty ? 'var(--surface)' : 'var(--primary)',
          border: isKitty ? '1.5px solid var(--line)' : 'none',
          boxShadow: 'var(--shadow-soft)',
        }}>
          {isStreaming && !message.content ? (
            <TypingDots />
          ) : (
            <MessageContent content={message.content} isUser={isUser} />
          )}
        </div>
        {showActions && (
          <div style={{ ...actionRowStyle, opacity: hovered ? 1 : 0 }}>
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
          </div>
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

function TypingDots() {
  return (
    <span style={{ display: 'flex', gap: 5, alignItems: 'center', height: 16 }}>
      <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink-2)', animation: 'dot1 1.2s ease-in-out infinite' }} />
      <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink-2)', animation: 'dot2 1.2s ease-in-out infinite' }} />
      <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ink-2)', animation: 'dot3 1.2s ease-in-out infinite' }} />
    </span>
  )
}

const actionRowStyle: CSSProperties = {
  display: 'flex', gap: 10, paddingLeft: 6,
  transition: 'opacity 0.12s linear',
}
const actionBtnStyle: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
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
