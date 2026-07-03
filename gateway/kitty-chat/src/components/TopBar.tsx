'use client'
import { useState } from 'react'
import type { CSSProperties } from 'react'
import { Chat, Model, STREAMING_LABEL } from '@/lib/types'
import { StateBadge, type CatState } from './CrayonCat'

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
  catState?: CatState
  onCommandPalette?: () => void
}

export function TopBar({
  activeModel,
  models,
  onSelectModel,
  showModelMenu,
  setShowModelMenu,
  isStreaming,
  modelFromGateway = true,
  catState = 'idle',
  onCommandPalette,
  isMobile = false,
  onToggleSidebar,
}: Props) {

  if (isMobile) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'calc(10px + env(safe-area-inset-top, 0px)) 16px 10px',
        borderBottom: '1.5px solid var(--line)',
        background: 'var(--surface)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          {onToggleSidebar && (
            <button onClick={onToggleSidebar} style={iconBtnStyle}>
              <svg viewBox="0 0 24 24" style={{ width: 18, height: 18 }}>
                <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
              </svg>
            </button>
          )}
          <span style={{
            fontFamily: 'var(--font-display)', fontWeight: 800,
            fontSize: 20, letterSpacing: '-0.02em', color: 'var(--ink)',
          }}>kitty</span>
          <StateBadge state={catState} />
        </div>
        <ModelSelector
          activeModel={activeModel}
          models={models}
          onSelectModel={onSelectModel}
          showModelMenu={showModelMenu}
          setShowModelMenu={setShowModelMenu}
          modelFromGateway={modelFromGateway}
        />
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 26px', height: 58,
      borderBottom: '1.5px solid var(--line)',
      background: 'var(--surface)', flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <span style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: 23, letterSpacing: '-0.02em', color: 'var(--ink)',
        }}>kitty</span>
        <StateBadge state={catState} />
        {isStreaming && (
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11,
            color: 'var(--c-yellow)',
          }}>{STREAMING_LABEL}</span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={onCommandPalette}
          style={chipBtnStyle}
        >⌘K</button>
        <button style={{ ...chipBtnStyle, color: 'var(--c-green)' }}>^_^ done</button>
        <button style={{ ...chipBtnStyle, color: 'var(--c-red)' }}>:[ broke</button>

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
          ...chipBtnStyle,
          display: 'flex', alignItems: 'center', gap: 6,
        }}
      >
        <span
          title={modelFromGateway ? undefined : 'Using offline model list'}
          style={{
            width: 7, height: 7, borderRadius: 99,
            background: modelFromGateway ? activeModel.color : 'var(--c-red)',
          }}
        />
        {activeModel.name}
      </button>

      {showModelMenu && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', right: 0,
          background: 'var(--surface)', border: '1.5px solid var(--line)',
          borderRadius: 12, minWidth: 200, zIndex: 100,
          boxShadow: 'var(--shadow)', padding: 6,
          display: 'flex', flexDirection: 'column', gap: 2,
        }}>
          {models.map(m => (
            <button
              key={m.id}
              onClick={() => { onSelectModel(m); setShowModelMenu(false) }}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                width: '100%', padding: '8px 12px', borderRadius: 8,
                background: m.id === activeModel.id ? 'var(--ginger-fade)' : 'transparent',
                border: 'none', cursor: 'pointer',
                fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 500,
                color: 'var(--ink)',
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: 99, background: m.color, flexShrink: 0 }} />
              {m.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const chipBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  border: '1.5px solid var(--line)',
  borderRadius: 8,
  padding: '4px 9px',
  background: 'transparent',
  cursor: 'pointer',
}

const iconBtnStyle: CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 36, height: 36, border: 'none', borderRadius: 12,
  background: 'transparent', color: 'var(--ink-2)', cursor: 'pointer',
}
