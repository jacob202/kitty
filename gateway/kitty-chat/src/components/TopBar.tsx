'use client'
import { useState, type CSSProperties } from 'react'
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
  activeView: string
  kittyMode: string
  onKittyModeChange: (mode: string) => void
  kittyModes?: Array<{ id: string; name: string }>
  sidebarCollapsed?: boolean
  onToggleSidebar?: () => void
}

const KITTY_MODES = [
  { id: 'default', name: 'Default' },
  { id: 'focus', name: 'Focus' },
  { id: 'explore', name: 'Explore' },
  { id: 'create', name: 'Create' },
]

export function TopBar({
  activeModel,
  models,
  onSelectModel,
  showModelMenu,
  setShowModelMenu,
  isStreaming,
  activeChat,
  modelFromGateway = true,
  activeView,
  kittyMode,
  onKittyModeChange,
  kittyModes = KITTY_MODES,
  sidebarCollapsed = false,
  onToggleSidebar,
}: Props) {
  const title = (() => {
    if (activeView === 'tasks') return 'Tasks'
    if (activeView === 'terminal') return 'Terminal'
    if (activeChat?.messages.length) return activeChat.title
    return getGreeting() + '.'
  })()

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: 56,
      padding: '0 20px',
      flexShrink: 0,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      position: 'relative',
      zIndex: 10,
      gap: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            style={{
              ...iconBtnStyle,
              background: 'transparent',
              color: 'var(--text-muted)',
              flexShrink: 0,
              width: 'auto',
              padding: '0 8px',
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.04em',
            }}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)' }}
          >
            {sidebarCollapsed ? 'Show' : 'Hide'}
          </button>
        )}

        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            letterSpacing: '0.02em',
          }}>{title}</div>
          {isStreaming && (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--tertiary)', marginTop: 2 }}>
              {STREAMING_LABEL}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <KittyModeSelector
          mode={kittyMode}
          modes={kittyModes}
          onChange={onKittyModeChange}
          compact={false}
        />

        <ModelSelector
          activeModel={activeModel}
          models={models}
          onSelectModel={onSelectModel}
          showModelMenu={showModelMenu}
          setShowModelMenu={setShowModelMenu}
          modelFromGateway={modelFromGateway}
        />
      </div>
    </div>
  )
}

function KittyModeSelector({
  mode,
  modes,
  onChange,
  compact = false,
}: {
  mode: string
  modes: Array<{ id: string; name: string }>
  onChange: (id: string) => void
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const current = modes.find(m => m.id === mode) ?? modes[0]

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          border: `1px solid ${open ? 'var(--border)' : 'transparent'}`,
          borderRadius: 8,
          padding: compact ? '4px 8px' : '6px 12px',
          background: open ? 'var(--surface-mid)' : 'var(--surface-low)',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: compact ? 10 : 12,
          fontWeight: 600,
          color: 'var(--text-dim)',
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={e => {
          if (!open) {
            const el = e.currentTarget as HTMLButtonElement
            el.style.background = 'var(--surface-mid)'
            el.style.color = 'var(--text)'
          }
        }}
        onMouseLeave={e => {
          if (!open) {
            const el = e.currentTarget as HTMLButtonElement
            el.style.background = 'var(--surface-low)'
            el.style.color = 'var(--text-dim)'
          }
        }}
      >
        <span>{current.name}</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 6px)',
          left: 0,
          background: 'var(--surface-high)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          overflow: 'hidden',
          minWidth: 140,
          zIndex: 100,
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
          padding: 6,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}>
          {modes.map(m => (
            <button
              key={m.id}
              onClick={() => { onChange(m.id); setOpen(false) }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '8px 12px',
                borderRadius: 8,
                background: m.id === mode ? 'var(--surface-mid)' : 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 600,
                color: m.id === mode ? 'var(--text)' : 'var(--text-dim)',
                transition: 'background 0.15s, color 0.15s',
              }}
              onMouseEnter={e => { if (m.id !== mode) {
                const el = e.currentTarget as HTMLButtonElement
                el.style.background = 'var(--surface-mid)'
                el.style.color = 'var(--text)'
              } }}
              onMouseLeave={e => { if (m.id !== mode) {
                const el = e.currentTarget as HTMLButtonElement
                el.style.background = 'transparent'
                el.style.color = 'var(--text-dim)'
              } }}
            >
              {m.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function ModelSelector({
  activeModel,
  models,
  onSelectModel,
  showModelMenu,
  setShowModelMenu,
  modelFromGateway,
}: {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  showModelMenu: boolean
  setShowModelMenu: (v: boolean) => void
  modelFromGateway?: boolean
}) {
  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setShowModelMenu(!showModelMenu)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          border: `1px solid ${showModelMenu ? 'var(--border)' : 'transparent'}`,
          borderRadius: 8,
          padding: '6px 12px',
          background: showModelMenu ? 'var(--surface-mid)' : 'var(--surface-low)',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--text-dim)',
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
        <span style={{ color: modelFromGateway ? 'inherit' : 'var(--text-muted)' }}>{activeModel.name}</span>
      </button>

      {showModelMenu && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 6px)',
          right: 0,
          background: 'var(--surface-high)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          overflow: 'hidden',
          minWidth: 200,
          zIndex: 100,
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
          padding: 6,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}>
          {models.map(m => (
            <button
              key={m.id}
              onClick={() => { onSelectModel(m); setShowModelMenu(false) }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '8px 12px',
                borderRadius: 8,
                background: m.id === activeModel.id ? 'var(--surface-mid)' : 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 600,
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
              {m.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 5) return 'still up'
  if (h < 12) return 'good morning'
  if (h < 17) return 'good afternoon'
  if (h < 21) return 'good evening'
  return 'late night'
}

const iconBtnStyle: CSSProperties = {
  width: 32,
  height: 32,
  display: 'grid',
  placeItems: 'center',
  borderRadius: 8,
  cursor: 'pointer',
  fontSize: 12,
  transition: 'all 0.2s ease',
}
