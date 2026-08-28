'use client'
import { useState } from 'react'
import type { CSSProperties } from 'react'
import { Model, STREAMING_LABEL } from '@/lib/types'
import { StateBadge, type CatState } from './CrayonCat'
import { ModelSelectorCmdk } from './ModelSelectorCmdk'

const SURFACE_LABELS: Record<string, string> = {
  home: 'Home',
  chat: 'Chat',
  work: 'Work',
  builder: 'Work',
  projects: 'Projects',
  studio: 'Image Lab',
  images: 'Image Lab',
  library: 'Library',
  settings: 'Settings',
}

interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  isStreaming: boolean
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
  runtimeState?: 'available' | 'unavailable' | 'degraded' | 'stale' | 'unknown'
  runtimeDetail?: string
  activeProject?: { id: number; name: string } | null
  projects?: Array<{ id: number; name: string }>
  onSelectProject?: (projectId: number) => void
  projectLoading?: boolean
  projectBusy?: boolean
}

export function TopBar({
  activeModel,
  models,
  onSelectModel,
  isStreaming,
  modelFromGateway = true,
  activeView,
  catState = 'idle',
  onCommandPalette,
  isMobile = false,
  onToggleSidebar,
  runtimeState = 'unknown',
  runtimeDetail,
  activeProject = null,
  projects = [],
  onSelectProject,
  projectLoading = false,
  projectBusy = false,
}: Props) {

  if (isMobile) {
    // Two rows on the phone. Squeezing a cat state, runtime, the active project
    // and the model selector into one row is what overflowed and clipped the
    // model selector (#346). Identity stays on the first row; the workspace and
    // model controls move to a second row where neither can push the other off
    // screen.
    return (
      <div style={{
        padding: 'calc(8px + env(safe-area-inset-top, 0px)) 12px 8px',
        borderBottom: '1px solid var(--color-separator)',
        background: 'var(--color-surface)', flexShrink: 0,
        display: 'grid', gap: 6,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, maxWidth: '100%' }} data-testid="topbar-identity-row">
          {onToggleSidebar && (
            <button aria-label="Open sidebar" onClick={onToggleSidebar} style={iconBtnStyle}>
              <svg viewBox="0 0 24 24" style={{ width: 18, height: 18 }}>
                <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
              </svg>
            </button>
          )}
          <span style={{
            fontFamily: 'var(--font-body)', fontWeight: 700,
            fontSize: 18, letterSpacing: '-0.02em', color: 'var(--color-text-primary)',
            flexShrink: 0,
          }}>kitty</span>
          <span style={{ flex: 1 }} />
          <StateBadge state={catState} />
          <RuntimeBadge state={runtimeState} detail={runtimeDetail} compact />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, maxWidth: '100%' }} data-testid="topbar-workspace-row">
          <div style={{ flex: 1, minWidth: 0 }}>
            <ProjectSelector
              activeProject={activeProject}
              projects={projects}
              onSelectProject={onSelectProject}
              loading={projectLoading}
              busy={projectBusy}
              compact
            />
          </div>
          <div style={{ minWidth: 0, maxWidth: '56%' }}>
            <ModelSelectorCmdk
              activeModel={activeModel}
              models={models}
              onSelectModel={onSelectModel}
              modelFromGateway={modelFromGateway}
              compact
            />
          </div>
        </div>
      </div>
    )
  }

  const surfaceLabel = SURFACE_LABELS[activeView] ?? 'Kitty'

  return (
    <header aria-label="Workspace toolbar" style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 20px', height: 'var(--topbar-height)',
      borderBottom: '1px solid var(--color-separator)',
      background: 'var(--color-surface)', flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <span style={{
          fontFamily: 'var(--font-body)', fontWeight: 650,
          fontSize: 18, letterSpacing: '-0.02em', color: 'var(--color-text-primary)',
        }}>{surfaceLabel}</span>
        <StateBadge state={catState} />
        <RuntimeBadge state={runtimeState} detail={runtimeDetail} />
        {isStreaming && (
          <span style={{
            fontFamily: 'var(--font-body)', fontSize: 12,
            color: 'var(--color-warning)',
          }}>{STREAMING_LABEL}</span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={onCommandPalette}
          title="command palette — search or jump anywhere"
          style={chipBtnStyle}
        >⌘K</button>
        <ProjectSelector
          activeProject={activeProject}
          projects={projects}
          onSelectProject={onSelectProject}
          loading={projectLoading}
          busy={projectBusy}
        />
        <ModelSelectorCmdk
          activeModel={activeModel}
          models={models}
          onSelectModel={onSelectModel}
          modelFromGateway={modelFromGateway}
        />
      </div>
    </header>
  )
}

function ProjectSelector({
  activeProject,
  projects,
  onSelectProject,
  loading,
  busy,
  compact = false,
}: {
  activeProject: { id: number; name: string } | null
  projects: Array<{ id: number; name: string }>
  onSelectProject?: (projectId: number) => void
  loading: boolean
  busy: boolean
  /** Phone header: a long project name pushed the model selector off-screen,
   *  so the select gets a hard cap and is allowed to shrink below it. */
  compact?: boolean
}) {
  if (loading) return <span style={projectStatusStyle}>project…</span>
  if (!projects.length || !onSelectProject) {
    return (
      <span
        title="No project scope is available"
        style={{ ...projectStatusStyle, ...(compact ? truncateStyle : {}) }}
      >
        project unavailable
      </span>
    )
  }
  return (
    <select
      aria-label="Active project"
      value={activeProject?.id ?? ''}
      disabled={busy}
      onChange={(event) => onSelectProject(Number(event.target.value))}
      style={{
        ...chipBtnStyle,
        maxWidth: compact ? 110 : 150,
        ...(compact ? { minWidth: 0, flexShrink: 1 } : {}),
      }}
    >
      {!activeProject && <option value="">select project</option>}
      {projects.map((project) => (
        <option key={project.id} value={project.id}>{project.name}</option>
      ))}
    </select>
  )
}

function RuntimeBadge({
  state,
  detail,
  compact = false,
}: {
  state: 'available' | 'unavailable' | 'degraded' | 'stale' | 'unknown'
  detail?: string
  /** Phone layout: the label wraps in the crowded top row, so show only the
   *  status dot and carry the words via title/aria-label instead. */
  compact?: boolean
}) {
  const healthy = state === 'available'
  const color = healthy ? 'var(--color-success)' : 'var(--color-destructive)'
  const label = healthy ? 'runtime live' : `runtime ${state}`
  return (
    <span
      title={detail ?? `runtime state: ${state}`}
      aria-label={label}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        fontFamily: 'var(--font-body)', fontSize: 11, whiteSpace: 'nowrap',
        color, borderRadius: 999,
        padding: compact ? 4 : '3px 4px', opacity: 0.92,
      }}
    >
      <span style={{ width: 5, height: 5, borderRadius: 99, background: color }} />
      {!compact && label}
    </span>
  )
}


const chipBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  color: 'var(--color-text-secondary)',
  border: '1px solid var(--color-separator)',
  borderRadius: 10,
  padding: '6px 9px',
  background: 'var(--color-surface)',
  cursor: 'pointer',
}

const iconBtnStyle: CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 44, height: 44, border: 'none', borderRadius: 12,
  background: 'transparent', color: 'var(--color-text-secondary)', cursor: 'pointer',
}

const projectStatusStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 11,
  color: 'var(--color-destructive)',
}

const truncateStyle: CSSProperties = {
  maxWidth: 110,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}
