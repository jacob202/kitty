'use client'
import { Chat, Model, STREAMING_LABEL } from '@/lib/types'

interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  showModelMenu: boolean
  setShowModelMenu: (v: boolean) => void
  isStreaming: boolean
  activeChat: Chat | null
  modelFromGateway?: boolean
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
  isStreaming, activeChat, modelFromGateway = true,
}: Props) {
  const face = isStreaming ? '=^._.^=' : '=^•ﻌ•^='
  const title = activeChat?.messages.length ? activeChat.title : greeting() + '.'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      height: 60, padding: '0 24px', flexShrink: 0,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      position: 'relative', zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
        <span style={{
          fontFamily: 'var(--font-ui)', fontSize: 22, flexShrink: 0,
          color: isStreaming ? 'var(--tertiary)' : 'var(--primary)',
          transition: 'color 0.3s ease',
        }}>{face}</span>
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
            color: 'var(--text)', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
            letterSpacing: '0.02em',
          }}>{title}</div>
          {isStreaming && (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--tertiary)', marginTop: 2 }}>
              {STREAMING_LABEL}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, position: 'relative' }}>
        <button
          onClick={() => setShowModelMenu(!showModelMenu)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            border: `1px solid ${showModelMenu ? 'var(--border)' : 'transparent'}`,
            borderRadius: 8, padding: '6px 12px',
            background: showModelMenu ? 'var(--surface-mid)' : 'var(--surface-low)',
            cursor: 'pointer', fontFamily: 'var(--font-mono)',
            fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={e => {
            if (!showModelMenu) {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = 'var(--surface-mid)'
              el.style.color = 'var(--text)'
            }
          }}
          onMouseLeave={e => {
            if (!showModelMenu) {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = 'var(--surface-low)'
              el.style.color = 'var(--text-dim)'
            }
          }}
        >
          <span
            title={modelFromGateway ? undefined : 'Using offline model list'}
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: modelFromGateway ? activeModel.color : 'var(--error)',
              flexShrink: 0,
              transition: 'background 0.3s',
            }}
          />
          <span style={{ color: modelFromGateway ? 'inherit' : 'var(--text-muted)' }}>{activeModel.name}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5, marginLeft: 2, transform: showModelMenu ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}>
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>

        {showModelMenu && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0,
            background: 'var(--surface-high)', border: '1px solid var(--border)',
            borderRadius: 12, overflow: 'hidden', minWidth: 200, zIndex: 100,
            boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
            padding: 6,
            display: 'flex', flexDirection: 'column', gap: 2,
          }}>
            {models.map(m => (
              <button
                key={m.id}
                onClick={() => { onSelectModel(m); setShowModelMenu(false) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '8px 12px', borderRadius: 8,
                  background: m.id === activeModel.id ? 'var(--surface-mid)' : 'transparent',
                  border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
                  color: m.id === activeModel.id ? 'var(--text)' : 'var(--text-dim)',
                  transition: 'background 0.15s, color 0.15s',
                }}
                onMouseEnter={e => { if (m.id !== activeModel.id) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.background = 'var(--surface-mid)'
                  el.style.color = 'var(--text)'
                } }}
                onMouseLeave={e => { if (m.id !== activeModel.id) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.background = 'transparent'
                  el.style.color = 'var(--text-dim)'
                } }}
              >
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: m.color, flexShrink: 0 }} />
                {m.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
