'use client'
import { Chat, Model, MODELS, CHAT_COLORS } from '@/lib/types'

interface Props {
  chats: Chat[]
  activeChatId: string | null
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onCloseChat: (id: string) => void
  activeModel: Model
  onSelectModel: (m: Model) => void
  showModelMenu: boolean
  setShowModelMenu: (v: boolean) => void
}

export function TopBar({
  chats, activeChatId, onSelectChat, onNewChat, onCloseChat,
  activeModel, onSelectModel, showModelMenu, setShowModelMenu,
}: Props) {
  return (
    <div style={{
      display: 'flex', alignItems: 'stretch',
      height: 58, background: 'var(--bg-raised)',
      borderBottom: '1px solid var(--border)', flexShrink: 0,
      position: 'relative', zIndex: 10,
    }}>
      {/* Wordmark */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '0 18px', borderRight: '1px solid var(--border)', flexShrink: 0,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 11, flexShrink: 0,
          backgroundImage: "url('/mascots/kitty-mission.png')",
          backgroundSize: '100% 100%',
        }} />
        <span style={{
          fontFamily: 'var(--font-ui)', fontSize: 24, fontWeight: 700, letterSpacing: 1,
          color: 'var(--text)', lineHeight: 1,
        }}>
          Kit<span style={{ color: 'var(--orange)' }}>ty</span>
        </span>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', alignItems: 'stretch', flex: 1, overflow: 'hidden' }}>
        {chats.map(chat => {
          const active = chat.id === activeChatId
          const col = CHAT_COLORS[chat.color]
          return (
            <button
              key={chat.id}
              onClick={() => onSelectChat(chat.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '0 16px', minWidth: 120, maxWidth: 200,
                fontFamily: 'var(--font-ui)', fontSize: 15, fontWeight: 600, letterSpacing: '0.3px',
                color: active ? 'var(--text)' : 'var(--text-faint)',
                background: active ? 'var(--bg)' : 'transparent',
                border: 'none', borderRight: '1px solid var(--border-dim)',
                cursor: 'pointer', whiteSpace: 'nowrap', position: 'relative',
                transition: 'color 0.1s, background 0.1s',
                boxShadow: active ? `inset 0 2px 0 ${col.tab}` : 'none',
              }}
              onMouseEnter={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.color = '#bbb' }}
              onMouseLeave={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-faint)' }}
            >
              <span style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: col.tab, boxShadow: `0 0 6px ${col.glow}`,
              }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, textAlign: 'left' }}>
                {chat.title}
              </span>
              <span
                onClick={e => { e.stopPropagation(); onCloseChat(chat.id) }}
                style={{ color: '#333', fontSize: 10, flexShrink: 0, cursor: 'pointer', padding: '0 2px' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#777')}
                onMouseLeave={e => (e.currentTarget.style.color = '#333')}
              >✕</span>
            </button>
          )
        })}
        <button
          onClick={onNewChat}
          style={{
            display: 'flex', alignItems: 'center', padding: '0 14px',
            color: 'var(--text-faint)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = '#888')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-faint)')}
        >+</button>
      </div>

      {/* Right controls */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 14px', borderLeft: '1px solid var(--border)', flexShrink: 0,
        position: 'relative',
      }}>
        <button
          onClick={() => setShowModelMenu(!showModelMenu)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            border: `1px solid ${showModelMenu ? 'var(--purple-glow)' : '#333'}`,
            borderRadius: 7, padding: '6px 14px', background: 'var(--bg-card)',
            cursor: 'pointer', fontFamily: 'var(--font-ui)',
            fontSize: 15, fontWeight: 600, color: 'var(--text)',
            transition: 'border-color 0.15s',
          }}
        >
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: activeModel.color,
            boxShadow: `0 0 8px ${activeModel.glow}`, flexShrink: 0,
          }} />
          <span style={{ color: activeModel.color }}>{activeModel.name}</span>
          <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>⌄</span>
        </button>

        {showModelMenu && (
          <div style={{
            position: 'absolute', top: '100%', right: 56, marginTop: 4,
            background: 'var(--bg-raised)', border: '1px solid var(--border)',
            borderRadius: 8, overflow: 'hidden', minWidth: 180, zIndex: 100,
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}>
            {MODELS.map(m => (
              <button
                key={m.id}
                onClick={() => { onSelectModel(m); setShowModelMenu(false) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '10px 14px',
                  background: m.id === activeModel.id ? 'var(--purple-dim)' : 'transparent',
                  border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--font-ui)', fontSize: 15, fontWeight: 600,
                  color: m.id === activeModel.id ? m.color : 'var(--text-muted)',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => { if (m.id !== activeModel.id) (e.currentTarget as HTMLButtonElement).style.background = '#1a1a1a' }}
                onMouseLeave={e => { if (m.id !== activeModel.id) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: m.color, boxShadow: `0 0 5px ${m.glow}` }} />
                {m.name}
              </button>
            ))}
          </div>
        )}

        {(['⌘', '≡'] as const).map(icon => (
          <button
            key={icon}
            style={{
              width: 34, height: 34, borderRadius: 6,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-faint)', fontSize: 16, cursor: 'pointer',
              border: '1px solid #2a2a2a', background: 'var(--bg-raised)',
              transition: 'color 0.1s, border-color 0.1s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text)'; (e.currentTarget as HTMLButtonElement).style.borderColor = '#444' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-faint)'; (e.currentTarget as HTMLButtonElement).style.borderColor = '#2a2a2a' }}
          >{icon}</button>
        ))}
      </div>
    </div>
  )
}
