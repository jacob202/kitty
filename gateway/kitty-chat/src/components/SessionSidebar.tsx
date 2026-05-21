'use client'
import { Chat, CHAT_COLORS } from '@/lib/types'

interface Props {
  chats: Chat[]
  activeChatId: string | null
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onCloseChat: (id: string) => void
}

function timeAgo(date: Date): string {
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 60) return 'now'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h'
  if (diff < 86400 * 7) return 'yday'
  return Math.floor(diff / 86400) + 'd'
}

export function SessionSidebar({ chats, activeChatId, onSelectChat, onNewChat, onCloseChat }: Props) {
  const sorted = [...chats].sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
  const cutoff = Date.now() - 24 * 3600 * 1000
  const today = sorted.filter(c => c.updatedAt.getTime() > cutoff)
  const older = sorted.filter(c => c.updatedAt.getTime() <= cutoff)

  return (
    <aside style={{
      width: 'var(--sidebar)',
      padding: '18px 14px',
      overflowY: 'auto',
      borderRight: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
          color: 'var(--text-muted)', letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>sessions</span>
        <button
          onClick={onNewChat}
          style={{
            background: 'var(--orange)', color: '#14100d',
            padding: '7px 10px', borderRadius: 12,
            fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: 12,
            boxShadow: '0 10px 28px rgba(232, 120, 69, 0.16)',
            cursor: 'pointer',
          }}
        >+ new</button>
      </div>

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
    </aside>
  )
}

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
      color: 'var(--text-muted)', letterSpacing: '0.14em', textTransform: 'uppercase',
      margin: '20px 0 6px',
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
        gap: 10,
        alignItems: 'center',
        padding: '10px 10px',
        borderRadius: 14,
        color: active ? 'var(--text)' : 'var(--text-dim)',
        background: active ? 'rgba(102, 119, 204, 0.09)' : 'transparent',
        border: `1px solid ${active ? 'rgba(102, 119, 204, 0.25)' : 'transparent'}`,
        width: '100%',
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'background 0.18s ease, border-color 0.18s ease',
        marginBottom: 2,
      }}
      onMouseEnter={e => {
        if (!active) {
          const el = e.currentTarget as HTMLButtonElement
          el.style.background = 'rgba(255,255,255,0.025)'
          el.style.borderColor = 'var(--border)'
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
        background: active ? 'var(--orange)' : dotColor,
        display: 'block', flexShrink: 0,
      }} />
      <span style={{ minWidth: 0 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 650,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          display: 'block',
        }}>{chat.title}</span>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 11 }}>{meta}</span>
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 11 }}>
          {timeAgo(chat.updatedAt)}
        </span>
        <span
          onClick={e => { e.stopPropagation(); onClose(chat.id) }}
          style={{ color: 'var(--text-ghost)', fontSize: 10, cursor: 'pointer', padding: '0 2px' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-ghost)')}
        >✕</span>
      </div>
    </button>
  )
}
