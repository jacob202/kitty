'use client'
import { Chat, CHAT_COLORS } from '@/lib/types'

interface Props {
  chats: Chat[]
  activeChatId: string | null
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onCloseChat: (id: string) => void
  collapsed?: boolean
}

function timeAgo(date: Date): string {
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 60) return 'now'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h'
  if (diff < 86400 * 7) return 'yday'
  return Math.floor(diff / 86400) + 'd'
}

export function SessionSidebar({ chats, activeChatId, onSelectChat, onNewChat, onCloseChat, collapsed = false }: Props) {
  const sorted = [...chats].sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
  const cutoff = Date.now() - 24 * 3600 * 1000
  const today = sorted.filter(c => c.updatedAt.getTime() > cutoff)
  const older = sorted.filter(c => c.updatedAt.getTime() <= cutoff)

  return (
    <aside style={{
      width: collapsed ? '60px' : 'var(--sidebar)',
      padding: collapsed ? '16px 12px' : '24px 16px',
      overflowY: 'auto',
      borderRight: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      flexShrink: 0,
      transition: 'width 0.2s ease, padding 0.2s ease',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'space-between',
        marginBottom: 20,
        minHeight: 32,
      }}>
        {!collapsed && (
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
            color: 'var(--text-muted)', letterSpacing: '0.14em', textTransform: 'uppercase',
          }}>sessions</span>
        )}
        <button
          onClick={onNewChat}
          style={{
            background: 'var(--primary)',
            color: '#fff',
            padding: collapsed ? '6px' : '6px 12px',
            borderRadius: 8,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            fontSize: 11,
            boxShadow: '0 4px 12px rgba(232, 120, 69, 0.15)',
            cursor: 'pointer',
            transition: 'background 0.2s',
            width: collapsed ? 32 : 'auto',
            height: collapsed ? 32 : 'auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
          }}
          title={collapsed ? 'New chat' : undefined}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--orange-deep)' }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--primary)' }}
        >
          {collapsed ? '+' : '+ new'}
        </button>
      </div>

      {!collapsed && (
        <>
          {today.length > 0 && (
            <>
              <GroupLabel>Today</GroupLabel>
              {today.map(c => (
                <SessionItem key={c.id} chat={c} active={c.id === activeChatId} onSelect={onSelectChat} onClose={onCloseChat} />
              ))}
            </>
          )}

          {older.length > 0 && (
            <>
              <GroupLabel>Earlier</GroupLabel>
              {older.map(c => (
                <SessionItem key={c.id} chat={c} active={c.id === activeChatId} onSelect={onSelectChat} onClose={onCloseChat} />
              ))}
            </>
          )}

          {chats.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--text-faint)', fontSize: 12, fontStyle: 'italic', marginTop: 20 }}>
              no sessions yet
            </div>
          )}
        </>
      )}

      {collapsed && chats.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
          {chats.slice(0, 5).map(c => (
            <div
              key={c.id}
              onClick={() => onSelectChat(c.id)}
              title={c.title}
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: CHAT_COLORS[c.color]?.tab || 'var(--indigo)',
                display: 'grid',
                placeItems: 'center',
                fontSize: 10,
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                border: c.id === activeChatId ? '2px solid var(--primary)' : '2px solid transparent',
                transition: 'border-color 0.2s ease',
              }}
            >
              {c.title.charAt(0).toUpperCase()}
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}
}

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
      color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase',
      margin: '24px 0 8px', paddingLeft: 4,
    }}>{children}</div>
  )
}

function SessionItem({ chat, active, onSelect, onClose }: {
  chat: Chat
  active: boolean
  onSelect: (id: string) => void
  onClose: (id: string) => void
}) {
  const dotColor = CHAT_COLORS[chat.color]?.tab ?? 'var(--indigo)'
  const lastMsg = chat.messages.at(-1)
  const meta = lastMsg?.role === 'assistant' ? 'kitty' : lastMsg ? 'you' : 'new'

  return (
    <button
      onClick={() => onSelect(chat.id)}
      style={{
        display: 'grid',
        gridTemplateColumns: '7px 1fr auto',
        gap: 12,
        alignItems: 'center',
        padding: '10px 12px',
        borderRadius: 10,
        color: active ? 'var(--text)' : 'var(--text-dim)',
        background: active ? 'var(--surface-mid)' : 'transparent',
        border: `1px solid ${active ? 'var(--border)' : 'transparent'}`,
        width: '100%',
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'background 0.2s ease, border-color 0.2s ease',
        marginBottom: 4,
      }}
      onMouseEnter={e => {
        if (!active) {
          const el = e.currentTarget as HTMLButtonElement
          el.style.background = 'var(--surface-low)'
          el.style.borderColor = 'var(--border-dim)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          const el = e.currentTarget as HTMLButtonElement
          el.style.background = 'transparent'
          el.style.borderColor = 'transparent'
        }
      }}
    >
      <span style={{
        width: 7, height: 24, borderRadius: 999,
        background: active ? 'var(--primary)' : dotColor,
        display: 'block', flexShrink: 0,
      }} />
      <span style={{ minWidth: 0 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          display: 'block', color: active ? 'var(--text)' : 'var(--text-dim)',
        }}>{chat.title}</span>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 10 }}>{meta}</span>
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 10 }}>
          {timeAgo(chat.updatedAt)}
        </span>
        <span
          onClick={e => { e.stopPropagation(); onClose(chat.id) }}
          style={{ color: 'var(--text-ghost)', fontSize: 11, cursor: 'pointer', padding: '0 4px', visibility: active ? 'visible' : 'hidden' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-ghost)')}
        >✕</span>
      </div>
    </button>
  )
}
