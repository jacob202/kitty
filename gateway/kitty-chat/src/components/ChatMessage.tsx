'use client'
import { isValidElement, useRef, useState, type ReactNode, type CSSProperties } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Copy, Check } from 'lucide-react'
import { Message, STREAMING_LABEL } from '@/lib/types'
import { MoodAvatar } from './MoodAvatar'
import { inferMood } from '@/lib/mood'

interface Props {
  message: Message
  isStreaming?: boolean
  initials: string
}

export function ChatMessage({ message, isStreaming, initials }: Props) {
  const isAI = message.role === 'assistant'
  const mood = isStreaming ? 'thinking' : (message.mood ?? inferMood(message.content, message.role))
  const time = message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <div
      style={{
        display: 'flex', gap: 12, padding: '10px 18px',
        alignItems: 'flex-start',
        borderBottom: '1px solid var(--border-dim)',
        background: isAI ? 'rgba(16, 20, 29, 0.4)' : 'transparent',
        transition: 'background 0.2s',
        animation: 'fadeSlideUp 0.3s ease',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = isAI ? 'rgba(16, 20, 29, 0.8)' : 'rgba(16, 20, 29, 0.3)')}
      onMouseLeave={e => (e.currentTarget.style.background = isAI ? 'rgba(16, 20, 29, 0.4)' : 'transparent')}
    >
      {/* Avatar */}
      {isAI ? (
        <MoodAvatar mood={mood} size={36} />
      ) : (
        <div style={{
          width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--surface-mid)',
          border: '1px solid var(--border)',
          fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: 'var(--text-muted)',
          letterSpacing: '0.5px',
        }}>
          {initials}
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
            color: isAI ? 'var(--text)' : 'var(--text-dim)',
          }}>
            {isAI ? 'Kitty' : 'You'}
          </span>
          <span style={{
            fontSize: 10,
            color: isStreaming ? 'var(--primary)' : 'var(--text-ghost)',
            fontFamily: 'var(--font-mono)',
          }}>
            {isStreaming ? STREAMING_LABEL : time}
          </span>
          {isAI && message.model && !isStreaming && (
            <span style={{
              fontSize: 10, color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              border: '1px solid var(--border)',
              borderRadius: 4, padding: '1px 6px', background: 'var(--surface-low)',
            }}>
              {message.model}
            </span>
          )}
        </div>

        {/* Content */}
        {isStreaming && !message.content ? (
          <TypingDots />
        ) : (
          <MessageContent content={message.content} />
        )}

        {/* Tags */}
        {message.tags && message.tags.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
            {message.tags.map(tag => (
              <span key={tag} style={{
                borderRadius: 4, padding: '3px 8px',
                fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600,
                background: 'var(--surface-high)', border: '1px solid var(--border)',
                color: 'var(--text-dim)',
              }}>
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function MessageContent({ content }: { content: string }) {
  return (
    <div style={bodyStyle}>
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

  // The remark-gfm AST renders <pre><code className="language-xxx">…</code></pre>;
  // sniff the language off the first child to label the block.
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
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          {lang || 'code'}
        </span>
        <button onClick={copy} style={copyBtnStyle} title="Copy">
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
    <div style={{ display: 'inline-flex', gap: 4, alignItems: 'center', padding: '4px 0' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)',
          display: 'inline-block', opacity: 0.6,
          animation: `bounce 1.4s infinite ease-in-out ${i * 0.16}s`,
        }} />
      ))}
    </div>
  )
}

// --- Markdown component styles ---

const bodyStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 15,
  lineHeight: 1.6,
  color: 'var(--text)',
  wordBreak: 'break-word',
}
const pStyle: CSSProperties = { margin: '0 0 10px' }
const h1Style: CSSProperties = { fontSize: 20, fontWeight: 700, margin: '14px 0 8px' }
const h2Style: CSSProperties = { fontSize: 17, fontWeight: 700, margin: '14px 0 8px' }
const h3Style: CSSProperties = { fontSize: 15, fontWeight: 700, margin: '12px 0 6px' }
const ulStyle: CSSProperties = { margin: '0 0 10px', paddingLeft: 22 }
const olStyle: CSSProperties = { margin: '0 0 10px', paddingLeft: 22 }
const liStyle: CSSProperties = { margin: '2px 0' }
const linkStyle: CSSProperties = { color: 'var(--primary)', textDecoration: 'underline', textUnderlineOffset: 2 }
const quoteStyle: CSSProperties = {
  margin: '8px 0',
  padding: '6px 12px',
  borderLeft: '3px solid var(--border)',
  color: 'var(--text-dim)',
  background: 'var(--surface-low)',
  borderRadius: '0 4px 4px 0',
}
const hrStyle: CSSProperties = { border: 0, borderTop: '1px solid var(--border-dim)', margin: '12px 0' }
const tableWrapStyle: CSSProperties = {
  margin: '8px 0 12px',
  overflowX: 'auto',
  border: '1px solid var(--border)',
  borderRadius: 6,
}
const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 13,
}
const thStyle: CSSProperties = {
  textAlign: 'left',
  padding: '6px 10px',
  background: 'var(--surface-mid)',
  borderBottom: '1px solid var(--border)',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.03em',
  color: 'var(--text)',
}
const tdStyle: CSSProperties = {
  padding: '6px 10px',
  borderTop: '1px solid var(--border-dim)',
  color: 'var(--text-dim)',
}
const codeBoxStyle: CSSProperties = {
  margin: '8px 0 12px',
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  overflow: 'hidden',
}
const codeBoxHeaderStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 10px',
  background: 'var(--surface-mid)',
  borderBottom: '1px solid var(--border)',
}
const copyBtnStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  background: 'transparent',
  border: 'none',
  padding: '2px 4px',
  color: 'var(--text-muted)',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  cursor: 'pointer',
  borderRadius: 4,
  transition: 'color 0.15s ease',
}
const preStyle: CSSProperties = {
  margin: 0,
  padding: '12px 14px',
  overflowX: 'auto',
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  lineHeight: 1.5,
}
const blockCodeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--text)',
  background: 'transparent',
}
const inlineCodeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  padding: '1px 6px',
  borderRadius: 4,
  background: 'var(--surface-low)',
  border: '1px solid var(--border-dim)',
  color: 'var(--primary-bright)',
}
