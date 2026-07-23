'use client'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { VIEWS, type ViewId } from '@/lib/views'

interface ViewRendererProps {
  view: string
  compact?: boolean
  theme?: string
  onToggleTheme?: () => void
  // Chat-specific props
  chatProps?: {
    messages: any[]
    chatId: string
    isStreaming: boolean
    catState: any
    onRetry: (id: string) => void
    onStartClick: () => void
    onChipClick: (chip: string) => void
  }
  // Home-specific props
  homeProps?: {
    preferredName: string
    onDecideInChat: (entry: any) => void
    onNavigate: (view: string) => void
  }
  // Builder-specific props
  builderProps?: {
    onBack: () => void
  }
  // Tasks/Work-specific
  workProps?: {
    isMobile: boolean
  }
  // Tools-specific
  toolsProps?: {
    loops: any[]
    insights: any[]
    promptTemplates: any[]
    onLoopToggle: (id: string) => void
    onInsightDismiss: (id: string) => void
    onInsightAction: (insightId: string, actionId: string) => void
    onPromptSelect: (content: string) => void
    loopsLoading: boolean
    insightsLoading: boolean
    promptsLoading: boolean
  }
}

export function ViewRenderer({
  view,
  compact = false,
  theme = 'cosmic',
  onToggleTheme,
  chatProps,
  homeProps,
  builderProps,
  workProps,
  toolsProps,
}: ViewRendererProps) {
  const id = view as ViewId
  const entry = VIEWS[id]

  if (!entry) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', fontSize: 14 }}>
        <span style={{ fontSize: 32, opacity: 0.3 }}>?</span>
        <span>{view} view</span>
        <span style={{ fontSize: 12 }}>coming soon</span>
      </div>
    )
  }

  const isMobile = compact
  const pad = { flex: 1, padding: isMobile ? '16px 12px 124px' : '20px 24px 40px' }

  return (
    <ErrorBoundary name={view}>
      <ViewBody
        view={id}
        pad={pad}
        isMobile={isMobile}
        theme={theme}
        onToggleTheme={onToggleTheme}
        chatProps={chatProps}
        homeProps={homeProps}
        builderProps={builderProps}
        workProps={workProps}
        toolsProps={toolsProps}
      />
    </ErrorBoundary>
  )
}

function ViewBody(props: ViewRendererProps & { pad: any; isMobile: boolean; view: ViewId }) {
  const { view, pad, isMobile, chatProps, homeProps, builderProps, workProps, toolsProps, theme, onToggleTheme } = props

  switch (view) {
    case 'home':
      return <HomeView {...homeProps} compact={isMobile} />
    case 'chat':
      return <ChatView {...chatProps} compact={isMobile} />
    case 'work':
    case 'tasks':
      return <WorkView isMobile={isMobile} />
    case 'studio':
    case 'images':
      return <StudioView isMobile={isMobile} />
    case 'builder':
      return (
        <div style={pad}>
          <BuilderView {...builderProps} />
        </div>
      )
    case 'library':
    case 'projects':
    case 'docs':
      return <LibraryView isMobile={isMobile} />
    case 'settings':
    case 'providers':
    case 'agents':
    case 'tools':
    case 'tutor':
      return <SettingsShell isMobile={isMobile} theme={(theme as ThemeMode) ?? 'cosmic'} onToggleTheme={onToggleTheme} />
    case 'terminal':
      return <TerminalView isMobile={isMobile} />
    default: {
      const _exhaustive: never = view as never
      void _exhaustive
      return null
    }
  }
}

// ── Individual view renderers (keep these here to avoid prop-drilling) ──

import { HomeState } from '@/components/HomeState'
function HomeView({ compact, preferredName, onDecideInChat, onNavigate }: any) {
  return (
    <HomeState
      compact={compact}
      preferredName={preferredName}
      onDecideInChat={onDecideInChat}
      onNavigate={onNavigate}
    />
  )
}

import { KittyThread } from '@/components/KittyThread'
function ChatView({ compact, ...props }: any) {
  return <KittyThread {...props} compact={compact} />
}

import { BuilderPanel } from '@/components/BuilderSurface'
function BuilderView({ onBack }: any) {
  return <BuilderPanel onBack={onBack} />
}

import { SettingsPanel } from '@/components/SettingsPanel'
import { ProviderCenter } from '@/components/ProviderCenter'
import { useState as useLocalState } from 'react'
import type { CatState } from '@/components/CrayonCat'

type ThemeMode = 'cosmic' | 'day' | 'night'

function SettingsShell({ isMobile, theme, onToggleTheme }: { isMobile: boolean; theme: ThemeMode; onToggleTheme?: () => void }) {
  const [tab, setTab] = useLocalState('general')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'providers', label: 'Providers' },
    { id: 'skills', label: 'Skills' },
    { id: 'advanced', label: 'Advanced' },
  ]

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--line)', paddingBottom: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px', border: 'none', background: tab === t.id ? 'var(--ginger-fade)' : 'transparent',
              color: tab === t.id ? 'var(--cat-ginger)' : 'var(--ink-2)',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid var(--cat-ginger)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && <SettingsPanel theme={theme} onToggleTheme={onToggleTheme!} />}
      {tab === 'providers' && <ProviderCenter />}
      {tab === 'skills' && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.8 }}>
          <p><strong>Tutor</strong> — learn, quiz, master</p>
          <p><strong>Agents</strong> — spawn, watch, stop autonomous workers</p>
          <p><strong>Tools</strong> — monitors, image gen, loops, insights, prompts</p>
          <p style={{ marginTop: 12, fontSize: 11 }}>These features are unrouted until they earn daily use. Launch from here or via command palette.</p>
        </div>
      )}
      {tab === 'advanced' && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink-2)' }}>
          <p>Theme: {theme}</p>
          <p>Advanced settings will appear here as features mature.</p>
        </div>
      )}
    </div>
  )
}

import { TaskPanel } from '@/components/TaskPanel'
import { TodoPanel } from '@/components/TodoPanel'
function WorkView({ isMobile }: { isMobile: boolean }) {
  return (
    <div style={{ flex: 1, padding: isMobile ? '16px 12px 124px' : '24px 32px 40px', display: 'grid', gap: 24, alignContent: 'start' }}>
      <TaskPanel />
      <TodoPanel />
    </div>
  )
}

import { ImageStudio } from '@/components/ImageStudio'
import { ImageGenPanel } from '@/components/ImageGenPanel'

function StudioView({ isMobile }: { isMobile: boolean }) {
  const [tab, setTab] = useLocalState('gallery')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--line)', padding: '8px 24px 0' }}>
        {[
          { id: 'gallery', label: 'Gallery' },
          { id: 'generate', label: 'Generate' },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px', border: 'none', background: tab === t.id ? 'var(--ginger-fade)' : 'transparent',
              color: tab === t.id ? 'var(--cat-ginger)' : 'var(--ink-2)',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid var(--cat-ginger)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div style={{ padding: pad, flex: 1, overflow: 'auto' }}>
        {tab === 'gallery' ? <ImageStudio /> : <ImageGenPanel />}
      </div>
    </div>
  )
}

import { ProjectsPanel } from '@/components/ProjectsPanel'
import { DocumentsPanel } from '@/components/DocumentsPanel'

function LibraryView({ isMobile }: { isMobile: boolean }) {
  const [filter, setFilter] = useLocalState('all')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 4 }}>
        {[
          { id: 'all', label: 'All' },
          { id: 'projects', label: 'Projects' },
          { id: 'docs', label: 'Documents' },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: '4px 12px', fontSize: 11, fontFamily: 'var(--font-mono)',
              border: '1.5px solid var(--line)', borderRadius: 99,
              background: filter === f.id ? 'var(--ginger-fade)' : 'transparent',
              color: filter === f.id ? 'var(--cat-ginger)' : 'var(--ink-2)',
              cursor: 'pointer',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>
      {(filter === 'all' || filter === 'projects') && <ProjectsPanel />}
      {(filter === 'all' || filter === 'docs') && <DocumentsPanel />}
    </div>
  )
}

import { TerminalStrip } from '@/components/TerminalStrip'
function TerminalView({ isMobile }: { isMobile: boolean }) {
  return (
    <div style={{ flex: 1, padding: isMobile ? '16px 12px 124px' : '24px 32px 40px', display: 'flex', flexDirection: 'column' }}>
      <TerminalStrip title="gateway log" maxLines={100} />
    </div>
  )
}
