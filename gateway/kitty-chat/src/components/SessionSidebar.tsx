'use client'
import { Chat } from '@/lib/types'

interface Props {
  chats: Chat[]
  activeChatId: string | null
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onCloseChat: (id: string) => void
}

export function SessionSidebar({ chats, activeChatId, onSelectChat, onNewChat, onCloseChat }: Props) {
  return (
    <aside style={{
      width: 'var(--sidebar)',
      height: '100vh',
      borderRight: '1px solid var(--border)',
      background: 'var(--bg-deep)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 14px 10px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          sessions
        </span>
        <button
          onClick={onNewChat}
          style={{
            background: 'transparent',
            border: '1px solid var(--border)',
            borderRadius: 6,
            color: 'var(--orange)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            padding: '3px 10px',
            cursor: 'pointer',
          }}
        >
          + new
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 8px' }}>
        {chats.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 12, padding: '12px 6px', fontFamily: 'var(--font-mono)' }}>
            no sessions yet
          </p>
        ) : (
          [...chats].reverse().map(chat => {
            const isActive = chat.id === activeChatId
            return (
              <div
                key={chat.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  borderRadius: 7,
                  marginBottom: 2,
                  background: isActive ? 'rgba(232, 120, 69, 0.10)' : 'transparent',
                  border: isActive ? '1px solid rgba(232, 120, 69, 0.22)' : '1px solid transparent',
                  transition: 'background 0.1s, border 0.1s',
                }}
              >
                <button
                  onClick={() => onSelectChat(chat.id)}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    textAlign: 'left',
                    padding: '8px 10px',
                    cursor: 'pointer',
                    minWidth: 0,
                  }}
                >
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12,
                    color: isActive ? 'var(--orange-2)' : 'var(--text-dim)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {chat.title === 'new chat'
                      ? (chat.messages[0]?.content.slice(0, 28) || 'new chat')
                      : chat.title}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                    {chat.messages.length} msg{chat.messages.length !== 1 ? 's' : ''}
                  </div>
                </button>
                <button
                  onClick={e => { e.stopPropagation(); onCloseChat(chat.id) }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-faint)',
                    cursor: 'pointer',
                    padding: '4px 8px',
                    fontSize: 14,
                    lineHeight: 1,
                    flexShrink: 0,
                  }}
                  aria-label="close"
                >
                  ×
                </button>
              </div>
            )
          })
        )}
      </div>
    </aside>
  )
}
