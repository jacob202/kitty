'use client'
import { Chat, KittyMood, Model } from '@/lib/types'
import { MoodAvatar } from './MoodAvatar'

interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  showModelMenu: boolean
  setShowModelMenu: (v: boolean) => void
  isStreaming: boolean
  activeChat: Chat | null
  kittyMood?: KittyMood
}

function greeting() {
  const h = new Date().getHours()
  if (h < 5) return 'still up'
  if (h < 12) return 'good morning'
  if (h < 17) return 'good afternoon'
  if (h < 21) return 'good evening'
  return 'late night'
}

export function TopBar({
  activeModel, models, onSelectModel, showModelMenu, setShowModelMenu,
  isStreaming, activeChat, kittyMood,
}: Props) {
  const liveMood: KittyMood = isStreaming ? 'thinking' : (kittyMood ?? 'idle')
  const title = activeChat?.messages.length ? activeChat.title : greeting() + '.'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      height: 56, padding: '0 20px', flexShrink: 0,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      position: 'relative', zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <MoodAvatar mood={liveMood} size={34} />
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700,
            color: 'var(--text)', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{title}</div>
          {isStreaming && (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--purple)', marginTop: 1 }}>
              thinking…
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, position: 'relative' }}>
        <button
          onClick={() => setShowModelMenu(!showModelMenu)}
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            border: `1px solid ${showModelMenu ? 'var(--border-soft)' : 'var(--border)'}`,
            borderRadius: 8, padding: '6px 12px',
            background: showModelMenu ? 'var(--panel-2)' : 'transparent',
            cursor: 'pointer', fontFamily: 'var(--font-mono)',
            fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
            transition: 'border-color 0.15s, background 0.15s',
          }}
          onMouseEnter={e => {
            if (!showModelMenu) {
              const el = e.currentTarget as HTMLButtonElement
              el.style.borderColor = 'var(--border-soft)'
              el.style.background = 'var(--panel-2)'
            }
          }}
          onMouseLeave={e => {
            if (!showModelMenu) {
              const el = e.currentTarget as HTMLButtonElement
              el.style.borderColor = 'var(--border)'
              el.style.background = 'transparent'
            }
          }}
        >
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: activeModel.color, flexShrink: 0 }} />
          <span style={{ color: activeModel.color }}>{activeModel.name}</span>
          <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>⌄</span>
        </button>

        {showModelMenu && (
          <div style={{
            position: 'absolute', top: '100%', right: 0, marginTop: 4,
            background: 'var(--panel)', border: '1px solid var(--border)',
            borderRadius: 10, overflow: 'hidden', minWidth: 190, zIndex: 100,
            boxShadow: 'var(--shadow)',
          }}>
            {models.map(m => (
              <button
                key={m.id}
                onClick={() => { onSelectModel(m); setShowModelMenu(false) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '10px 14px',
                  background: m.id === activeModel.id ? 'var(--purple-dim)' : 'transparent',
                  border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
                  color: m.id === activeModel.id ? m.color : 'var(--text-muted)',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => { if (m.id !== activeModel.id) (e.currentTarget as HTMLButtonElement).style.background = 'var(--panel-2)' }}
                onMouseLeave={e => { if (m.id !== activeModel.id) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: m.color, flexShrink: 0 }} />
                {m.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
