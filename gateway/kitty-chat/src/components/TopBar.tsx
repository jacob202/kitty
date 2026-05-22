'use client'
import { useState } from 'react'
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
  onViewChange: (view: string) => void
  kittyMode: string
  onKittyModeChange: (mode: string) => void
  sidebarCollapsed?: boolean
  onToggleSidebar?: () => void
}

const VIEWS = [
  { id: 'home', label: 'Home' },
  { id: 'chat', label: 'Chat' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'terminal', label: 'Terminal' },
] as const

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
  onViewChange,
  kittyMode,
  onKittyModeChange,
  kittyModes = KITTY_MODES,
}: Props) {
  const face = isStreaming ? '=^._.^=' : '=^•ﻌ•^='
  const title = activeChat?.messages.length ? activeChat.title : getGreeting() + '.'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: 60,
      padding: '0 16px',
      flexShrink: 0,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      position: 'relative',
      zIndex: 10,
      gap: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0 }}>
        <span style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 22,
          flexShrink: 0,
          color: isStreaming ? 'var(--tertiary)' : 'var(--primary)',
          transition: 'color 0.3s ease',
        }}>{face}</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              style={{
                ...iconBtnStyle,
                background: 'transparent',
                color: 'var(--text-muted)',
              }}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {sidebarCollapsed ? '▶' : '◀'}
            </button>
          )}
          {VIEWS.map(view => (
            <button
              key={view.id}
              onClick={() => onViewChange(view.id)}
              style={{
                ...tabStyle,
                background: activeView === view.id ? 'var(--surface-mid)' : 'transparent',
                color: activeView === view.id ? 'var(--text)' : 'var(--text-muted)',
                borderBottom: activeView === view.id ? `2px solid var(--primary)` : '2px solid transparent',
              }}
              onMouseEnter={e => {
                if (activeView !== view.id) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.background = 'var(--surface-low)'
                  el.style.color = 'var(--text)'
                }
              }}
              onMouseLeave={e => {
                if (activeView !== view.id) {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.background = 'transparent'
                  el.style.color = 'var(--text-muted)'
                }
              }}
            >
              {view.label}
            </button>
          ))}
        </div>

        <div style={{ minWidth: 0 }}>
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
        < KittyModeSelector
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
        <span style={{ color: 'var(--purple)', fontSize: 12 }}>◉</span>
        <span>{current.name}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5, marginLeft: 2, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}>
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
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
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: m.id === mode ? 'var(--purple)' : 'var(--text-muted)', flexShrink: 0 }} />
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
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: m.color, flexShrink: 0 }} />
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

const tabStyle: CSSProperties = {
  padding: '8px 16px',
  borderRadius: 8,
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  fontWeight: 600,
  transition: 'all 0.2s ease',
  border: 'none',
  borderBottom: '2px solid transparent',
  background: 'transparent',
  marginBottom: '-2px',
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
