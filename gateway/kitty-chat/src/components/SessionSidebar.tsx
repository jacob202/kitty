'use client'
import { useState } from 'react'
import { Chat } from '@/lib/types'

interface Props {
  chats: Chat[]
  activeChatId: string | null
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onCloseChat: (id: string) => void
  collapsed?: boolean
  width?: string | number
}

function timeAgo(date: Date): string {
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 60) return 'now'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h'
  if (diff < 86400 * 2) return '1d'
  return Math.floor(diff / 86400) + 'd'
}

const SECTION_COLORS: Record<string, string> = {
  pinned: 'var(--c-red)',
  today: 'var(--c-blue)',
  yesterday: 'var(--c-green)',
  earlier: 'var(--c-purple)',
}

export function SessionSidebar({ chats, activeChatId, onSelectChat, onNewChat, onCloseChat }: Props) {
  const [search, setSearch] = useState('')

  const sorted = [...chats].sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
  const now = Date.now()
  const dayMs = 86400 * 1000

  const today = sorted.filter(c => (now - c.updatedAt.getTime()) < dayMs)
  const yesterday = sorted.filter(c => (now - c.updatedAt.getTime()) >= dayMs && (now - c.updatedAt.getTime()) < dayMs * 2)
  const earlier = sorted.filter(c => (now - c.updatedAt.getTime()) >= dayMs * 2)

  const q = search.trim().toLowerCase()
  const groups: { key: string; label: string; items: Chat[] }[] = q
    ? [{ key: 'results', label: sorted.filter(c => c.title.toLowerCase().includes(q)).length ? 'results' : 'nothing here', items: sorted.filter(c => c.title.toLowerCase().includes(q)) }]
    : [
        ...(today.length ? [{ key: 'today', label: 'today', items: today }] : []),
        ...(yesterday.length ? [{ key: 'yesterday', label: 'yesterday', items: yesterday }] : []),
        ...(earlier.length ? [{ key: 'earlier', label: 'earlier', items: earlier }] : []),
      ]

  return (
    <aside style={{
      width: 268,
      background: 'var(--surface)',
      borderRight: '1.5px solid var(--line)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      <div style={{ padding: '16px 14px 10px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button
          onClick={onNewChat}
          style={{
            width: '100%', border: 'none', borderRadius: 12,
            background: 'var(--primary)', color: 'var(--on-primary)',
            padding: 11,
            fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 14,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
            boxShadow: 'var(--btn-shadow)',
          }}
        >
          <span style={{ fontSize: 18, lineHeight: 1 }}>+</span> new chat
        </button>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--surface-2)', border: '1.5px solid var(--line)',
          borderRadius: 11, padding: '8px 11px',
        }}>
          <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, color: 'var(--ink-2)', flexShrink: 0 }}>
            <path d="M11 4 a7 7 0 1 0 0 14 a7 7 0 0 0 0 -14 M16 16 L21 21" stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" filter="url(#wob)" />
          </svg>
          <input
            type="text"
            placeholder="search chats"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              flex: 1, border: 'none', background: 'transparent',
              fontFamily: 'var(--font-body)', fontSize: 13,
              color: 'var(--ink)', outline: 'none',
            }}
          />
        </div>
      </div>

      <div style={{ overflowY: 'auto', flex: 1, padding: '2px 10px 12px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {groups.map(g => (
          <div key={g.key} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, padding: '0 4px', marginBottom: 2 }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 10,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                color: 'var(--ink-2)',
              }}>{g.label}</span>
              <svg viewBox="0 0 80 7" preserveAspectRatio="none" style={{ width: 46, height: 6 }}>
                <path d="M2 5 Q22 1 40 4 T78 3.5" stroke={SECTION_COLORS[g.key] ?? 'var(--c-blue)'} strokeWidth={2.4} fill="none" strokeLinecap="round" filter="url(#wob)" />
              </svg>
            </div>
            {g.items.map(chat => (
              <SessionRow
                key={chat.id}
                chat={chat}
                active={chat.id === activeChatId}
                dotColor={SECTION_COLORS[g.key] ?? 'var(--c-blue)'}
                onSelect={onSelectChat}
                onClose={onCloseChat}
              />
            ))}
          </div>
        ))}

        {chats.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--ink-2)', fontSize: 12, marginTop: 20 }}>
            nothing here yet
          </div>
        )}
      </div>

      <div style={{
        padding: '11px 14px',
        borderTop: '1.5px solid var(--line)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--c-green)' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }}>
          all synced · audience of one
        </span>
      </div>
    </aside>
  )
}

function SessionRow({ chat, active, dotColor, onSelect, onClose }: {
  chat: Chat
  active: boolean
  dotColor: string
  onSelect: (id: string) => void
  onClose: (id: string) => void
}) {
  const lastMsg = chat.messages.at(-1)
  const preview = lastMsg?.content?.slice(0, 40) || 'new chat'

  return (
    <button
      onClick={() => onSelect(chat.id)}
      style={{
        width: '100%', display: 'flex', alignItems: 'flex-start', gap: 9,
        border: 'none', borderRadius: 10,
        padding: '8px 9px', cursor: 'pointer',
        background: active ? 'var(--ginger-fade)' : 'transparent',
        textAlign: 'left',
      }}
    >
      <span style={{
        width: 9, height: 9, borderRadius: 3,
        background: dotColor, flexShrink: 0, marginTop: 4,
      }} />
      <span style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0, flex: 1 }}>
        <span style={{
          fontSize: 13, fontWeight: 600, color: 'var(--ink)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{chat.title}</span>
        <span style={{
          fontSize: 11.5, color: 'var(--ink-2)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{preview}</span>
      </span>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 10,
        color: 'var(--ink-2)', flexShrink: 0, marginTop: 3,
      }}>{timeAgo(chat.updatedAt)}</span>
    </button>
  )
}
