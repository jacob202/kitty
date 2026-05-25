'use client'
import { useState } from 'react'
import { Message, STREAMING_LABEL } from '@/lib/types'

interface Props {
  message: Message
  isStreaming?: boolean
  initials: string
}

export function ChatMessage({ message, isStreaming, initials }: Props) {
  const isAI = message.role === 'assistant'

  const time = message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  const avatarStyle = {
    width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'var(--surface-mid)',
    border: '1px solid var(--border)',
    fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
    color: isAI ? 'var(--primary)' : 'var(--text-muted)',
    letterSpacing: '0.5px',
  } as const

  return (
    <div
      style={{
        display: 'flex', gap: 16, padding: '16px 24px',
        alignItems: 'flex-start',
        borderBottom: '1px solid var(--border-dim)',
        borderLeft: isAI ? '2px solid var(--primary)' : '2px solid transparent',
        paddingLeft: 22,
        background: isAI ? 'rgba(16, 20, 29, 0.4)' : 'transparent',
        transition: 'background 0.2s',
        animation: 'fadeSlideUp 0.3s ease',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = isAI ? 'rgba(16, 20, 29, 0.8)' : 'rgba(16, 20, 29, 0.3)')}
      onMouseLeave={e => (e.currentTarget.style.background = isAI ? 'rgba(16, 20, 29, 0.4)' : 'transparent')}
    >
      <div style={avatarStyle}>
        {isAI ? 'K' : initials}
      </div>

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

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false)
  function handleCopy() {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <div style={{
      marginTop: 12, marginBottom: 12,
      background: 'var(--surface-low)',
      border: '1px solid var(--border)',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        background: 'var(--surface-mid)', borderBottom: '1px solid var(--border)',
        padding: '6px 12px', color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>{lang}</span>
        <span
          onClick={handleCopy}
          style={{ fontSize: 10, opacity: copied ? 1 : 0.5, cursor: 'pointer', color: copied ? 'var(--mint)' : undefined, transition: 'color 0.2s, opacity 0.2s' }}
        >{copied ? 'Copied!' : 'Copy'}</span>
      </div>
      <pre style={{
        padding: '12px 14px', margin: 0,
        fontSize: 13, lineHeight: 1.5, color: 'var(--text)',
        overflowX: 'auto', fontFamily: 'var(--font-mono)',
      }}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

function MessageContent({ content }: { content: string }) {
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <div style={{ fontSize: 15, lineHeight: 1.6, fontFamily: 'var(--font-ui)', color: 'var(--text)', wordBreak: 'break-word' }}>
      {parts.map((part, i) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).split('\n')
          const lang = lines[0].trim()
          const code = lines.slice(1).join('\n')
          return <CodeBlock key={i} lang={lang} code={code} />
        }
        return (
          <span key={i} style={{ whiteSpace: 'pre-wrap' }}>{part}</span>
        )
      })}
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
