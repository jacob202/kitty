'use client'
import { useState, type ReactNode } from 'react'
import type { CSSProperties } from 'react'
import { Chat, Model, STREAMING_LABEL } from '@/lib/types'
import {
  House,
  MessageSquare,
  CheckSquare,
  Terminal,
  Wrench,
  PanelLeft,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Sparkles,
} from 'lucide-react'

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
  kittyModes?: Array<{ id: string; name: string }>
  sidebarCollapsed?: boolean
  onToggleSidebar?: () => void
  isMobile?: boolean
}

const VIEWS: Array<{ id: string; label: string; icon: ReactNode }> = [
  { id: 'home', label: 'home', icon: <House size={14} /> },
  { id: 'chat', label: 'chat', icon: <MessageSquare size={14} /> },
  { id: 'tasks', label: 'tasks', icon: <CheckSquare size={14} /> },
  { id: 'tools', label: 'tools', icon: <Wrench size={14} /> },
  { id: 'terminal', label: 'terminal', icon: <Terminal size={14} /> },
]

const KITTY_MODES = [
  { id: 'default', name: 'default' },
  { id: 'focus', name: 'focus' },
  { id: 'explore', name: 'explore' },
  { id: 'create', name: 'create' },
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
  sidebarCollapsed = false,
  onToggleSidebar,
  isMobile = false,
}: Props) {
  const activeViewMeta = VIEWS.find(view => view.id === activeView)
  const title = activeChat?.messages.length
    ? activeChat.title
    : activeView === 'home'
      ? getGreeting() + '.'
      : activeViewMeta?.label ?? 'kitty'

  if (isMobile) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: 'calc(10px + env(safe-area-inset-top, 0px)) 12px 8px',
        flexShrink: 0,
        borderBottom: '1px solid var(--border)',
        background: 'rgba(26, 20, 16, 0.92)',
        position: 'relative',
        zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/kitty-mascot.svg"
              alt="Kitty"
              width={34}
              height={34}
              style={{
                flexShrink: 0,
                display: 'block',
                filter: isStreaming ? 'saturate(1.35) brightness(1.08)' : 'none',
                transition: 'filter 0.3s ease',
              }}
            />
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 700,
                color: 'var(--text)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                letterSpacing: '0.02em',
              }}>{title}</div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: isStreaming ? 'var(--tertiary)' : 'var(--text-muted)',
                marginTop: 2,
              }}>
                {isStreaming
                  ? STREAMING_LABEL
                  : modelFromGateway
                    ? activeModel.name
                    : `${activeModel.name} · offline models`}
              </div>
            </div>
          </div>

          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              style={{
                ...iconBtnStyle,
                width: 36,
                height: 36,
                background: 'var(--surface-low)',
                color: 'var(--text-dim)',
                flexShrink: 0,
              }}
              title="Open sessions"
            >
              <PanelLeft size={16} />
            </button>
          )}
        </div>

        <div style={{
          display: 'flex',
          gap: 6,
          overflowX: 'auto',
          paddingBottom: 2,
          scrollbarWidth: 'none',
          msOverflowStyle: 'none',
        }}>
          {VIEWS.map(view => (
            <button
              key={view.id}
              onClick={() => onViewChange(view.id)}
              style={{
                ...tabStyle,
                padding: '8px 10px',
                flexShrink: 0,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: activeView === view.id ? 'var(--surface-mid)' : 'transparent',
                color: activeView === view.id ? 'var(--text)' : 'var(--text-muted)',
                borderBottom: activeView === view.id ? '2px solid var(--primary)' : '2px solid transparent',
              }}
            >
              {view.icon}
              {view.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 8 }}>
          <KittyModeSelector
            mode={kittyMode}
            modes={kittyModes}
            onChange={onKittyModeChange}
            compact={true}
          />
          <ModelSelector
            activeModel={activeModel}
            models={models}
            onSelectModel={onSelectModel}
            showModelMenu={showModelMenu}
            setShowModelMenu={setShowModelMenu}
            modelFromGateway={modelFromGateway}
            compact={true}
          />
        </div>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: 60,
      padding: '0 16px',
      flexShrink: 0,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(26, 20, 16, 0.92)',
      position: 'relative',
      zIndex: 10,
      gap: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/kitty-mascot.svg"
          alt="Kitty"
          width={44}
          height={44}
          style={{
            flexShrink: 0,
            display: 'block',
            filter: isStreaming ? 'saturate(1.35) brightness(1.08)' : 'none',
            transition: 'filter 0.3s ease',
          }}
        />

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
              {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
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
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                {view.icon}
                {view.label}
              </span>
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
    <div style={{ position: 'relative', width: compact ? '100%' : undefined }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: compact ? 'space-between' : undefined,
          gap: 6,
          width: compact ? '100%' : undefined,
          border: `1px solid ${open ? 'var(--border)' : 'transparent'}`,
          borderRadius: 4,
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
        <Sparkles size={12} color="var(--purple)" />
        <span>{current.name}</span>
        <ChevronDown size={12} style={{ opacity: 0.5, marginLeft: 2, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }} />
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 6px)',
          left: 0,
          background: 'var(--surface-high)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          overflow: 'hidden',
          minWidth: 140,
          zIndex: 100,
          boxShadow: '4px 4px 0 var(--ink-deep)',
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
                borderRadius: 4,
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
  compact = false,
}: {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  showModelMenu: boolean
  setShowModelMenu: (v: boolean) => void
  modelFromGateway?: boolean
  compact?: boolean
}) {
  return (
    <div style={{ position: 'relative', width: compact ? '100%' : undefined }}>
      <button
        onClick={() => setShowModelMenu(!showModelMenu)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: compact ? 'space-between' : undefined,
          gap: 8,
          width: compact ? '100%' : undefined,
          border: `1px solid ${showModelMenu ? 'var(--border)' : 'transparent'}`,
          borderRadius: 4,
          padding: compact ? '4px 8px' : '6px 12px',
          background: showModelMenu ? 'var(--surface-mid)' : 'var(--surface-low)',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: compact ? 10 : 12,
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
        <ChevronDown size={12} style={{ opacity: 0.5, marginLeft: 2, transform: showModelMenu ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }} />
      </button>

      {showModelMenu && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 6px)',
          right: 0,
          background: 'var(--surface-high)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          overflow: 'hidden',
          minWidth: 200,
          zIndex: 100,
          boxShadow: '4px 4px 0 var(--ink-deep)',
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
                borderRadius: 4,
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
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', minWidth: 0 }}>
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.name}</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 500 }}>{m.id}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'good morning'
  if (hour < 18) return 'good afternoon'
  return 'good evening'
}

const tabStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  height: 36,
  padding: '0 12px',
  border: 'none',
  borderRadius: 4,
  background: 'transparent',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  fontWeight: 600,
  transition: 'all 0.2s ease',
}

const iconBtnStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 32,
  height: 32,
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  transition: 'all 0.2s ease',
}
