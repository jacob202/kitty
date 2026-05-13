'use client'
import { Message } from '@/lib/types'
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
        display: 'flex', gap: 14, padding: '14px 20px',
        alignItems: 'flex-start',
        borderBottom: '1px solid var(--border-dim)',
        borderLeft: `3px solid ${isAI ? 'color-mix(in srgb, var(--purple) 12%, transparent)' : 'color-mix(in srgb, var(--orange) 15%, transparent)'}`,
        transition: 'background 0.1s',
        animation: 'fadeSlideUp 0.2s ease',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = '#141414')}
      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
    >
      {/* Avatar */}
      {isAI ? (
        <MoodAvatar mood={mood} size={52} />
      ) : (
        <div style={{
          width: 52, height: 52, borderRadius: 12, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg, #2d1208, #1a0800)',
          border: '1.5px solid color-mix(in srgb, var(--orange) 40%, transparent)',
          boxShadow: '0 0 12px color-mix(in srgb, var(--orange) 13%, transparent)',
          fontFamily: 'var(--font-ui)', fontSize: 16, fontWeight: 700, color: 'var(--orange)',
          letterSpacing: '0.5px', marginTop: 2,
        }}>
          {initials}
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
          <span style={{
            fontFamily: 'var(--font-ui)', fontSize: 18, fontWeight: 700, lineHeight: 1, letterSpacing: '0.5px',
            color: isAI ? 'var(--purple-2)' : '#ff7a52',
            textShadow: isAI ? '0 0 10px color-mix(in srgb, var(--purple) 33%, transparent)' : '0 0 8px color-mix(in srgb, var(--orange) 20%, transparent)',
          }}>
            {isAI ? 'KITTY' : 'YOU'}
          </span>
          <span style={{ fontSize: 11, color: isStreaming ? 'color-mix(in srgb, var(--purple) 27%, transparent)' : 'var(--text-ghost)', fontFamily: 'var(--font-mono)' }}>
            {isStreaming ? 'thinking…' : time}
          </span>
          {isAI && message.model && !isStreaming && (
            <span style={{
              fontSize: 10, color: 'color-mix(in srgb, var(--purple) 53%, transparent)',
              fontFamily: 'var(--font-mono)',
              border: '1px solid color-mix(in srgb, var(--purple) 13%, transparent)',
              borderRadius: 4, padding: '1px 6px', background: 'var(--purple-dim)',
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
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
            {message.tags.map(tag => (
              <span key={tag} style={{
                borderRadius: 20, padding: '4px 10px',
                fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600, letterSpacing: '0.3px',
                background: 'var(--teal-dim)', border: '1px solid color-mix(in srgb, var(--teal) 40%, transparent)',
                color: 'var(--teal)',
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
  // Split on code blocks
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <div style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--text-dim)' }}>
      {parts.map((part, i) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).split('\n')
          const lang = lines[0]
          const code = lines.slice(1).join('\n')
          return (
            <pre key={i} style={{
              marginTop: 10, background: '#141414',
              border: '1px solid #222', borderLeft: '3px solid var(--teal)',
              borderRadius: 6, padding: '14px 16px',
              fontSize: 13, lineHeight: 1.7, color: '#888',
              overflowX: 'auto', fontFamily: 'var(--font-mono)',
            }}>
              {lang && <div style={{ color: '#333', fontSize: 10, marginBottom: 8 }}>{lang}</div>}
              <code>{code}</code>
            </pre>
          )
        }
        // Inline: render plain text, preserving line breaks
        return (
          <span key={i} style={{ whiteSpace: 'pre-wrap' }}>{part}</span>
        )
      })}
    </div>
  )
}

function TypingDots() {
  return (
    <div style={{ display: 'inline-flex', gap: 6, alignItems: 'center', padding: '8px 0' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 8, height: 8, borderRadius: '50%', background: 'var(--purple)',
          display: 'inline-block',
          animation: `bounce 1.2s infinite ${i * 0.2}s`,
        }} />
      ))}
    </div>
  )
}
