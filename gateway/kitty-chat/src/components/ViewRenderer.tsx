'use client'

import dynamic from 'next/dynamic'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { TodoPanel } from './TodoPanel'

// -- lazy-loaded view components ------------------------------------------------

const HomeView = dynamic(() => import('./HomeView'))
const ChatView = dynamic(() => import('./ChatView'))
const BuilderView = dynamic(() => import('./BuilderView'))
const SettingsShell = dynamic(() => import('./SettingsShell'))
const WorkView = dynamic(() => import('./WorkView'))
const StudioView = dynamic(() => import('./StudioView'))
const ProjectsView = dynamic(() => import('./ProjectsView'))
const LibraryView = dynamic(() => import('./LibraryView'))
const AutomationsView = dynamic(() => import('./AutomationsView'))
const TutorShell = dynamic(() => import('./TutorShell'))
const JournalPanel = dynamic(() => import('./JournalPanel'))
const TerminalView = dynamic(() => import('./TerminalView'))
const AgentWorkspacePanel = dynamic(() => import('./AgentWorkspacePanel').then((mod) => mod.AgentWorkspacePanel))

// -- view renderer --------------------------------------------------------------

interface ViewRendererProps {
  view: string
  compact?: boolean
  theme?: string
  onToggleTheme?: () => void
  chatProps?: {
    messages: any[]
    chatId: string
    isStreaming: boolean
    catState: any
    onRetry: (id: string) => void
    retryBranches?: Record<number, any[][]>
    onSwitchBranch?: (messageIndex: number, branchIndex: number) => void
    onStartClick: () => void
    onChipClick: (chip: string) => void
  }
  homeProps?: {
    preferredName: string
    onDecideInChat: (entry: any) => void
    onNavigate: (view: string) => void
    onExpertClick?: (expert: any) => void
  }
  builderProps?: { onBack: () => void }
  workProps?: { isMobile: boolean }
  toolsProps?: {
    loops: any[]
    insights: any[]
    promptTemplates: any[]
    onLoopToggle: (id: string) => void
    onInsightDismiss: (id: string) => void
    onInsightAction: (insightId: string, actionId: string) => void
    onPromptSelect: (content: string) => void
    loopsLoading: boolean
    loopsError?: string | null
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
  const isMobile = compact
  const pad = { flex: 1, padding: isMobile ? '16px 12px 124px' : '20px 24px 40px' }
  const themeMode = theme as 'cosmic' | 'day' | 'night'

  const body = (() => {
    switch (view) {
      case 'home':
        return <HomeView {...homeProps} compact={isMobile} />
      case 'chat':
        return <ChatView {...chatProps} compact={isMobile} />
      case 'work':
        return <WorkView isMobile={isMobile} onNavigate={homeProps?.onNavigate} />
      case 'tasks':
        return <div style={pad}><TodoPanel /></div>
      case 'studio':
      case 'images':
        return <StudioView isMobile={isMobile} />
      case 'builder-details':
        return <div style={pad}><BuilderView {...builderProps} isMobile={isMobile} /></div>
      case 'builder':
        return <WorkView isMobile={isMobile} onNavigate={homeProps?.onNavigate} />
      case 'agents':
        return <AgentWorkspacePanel />
      case 'library':
      case 'docs':
        return <LibraryView isMobile={isMobile} />
      case 'projects':
        return <ProjectsView isMobile={isMobile} />
      case 'automations':
        return <AutomationsView isMobile={isMobile} loops={toolsProps?.loops ?? []} loopsLoading={toolsProps?.loopsLoading ?? false} loopsError={toolsProps?.loopsError ?? null} onLoopToggle={toolsProps?.onLoopToggle ?? (() => {})} />
    case 'settings':
    case 'providers':
    case 'tools':
      return <SettingsShell isMobile={isMobile} theme={(theme as 'cosmic' | 'day' | 'night') ?? 'cosmic'} onToggleTheme={onToggleTheme} />
    case 'tutor':
      return <TutorShell isMobile={isMobile} />
    case 'journal':
      return <div style={pad}><JournalPanel /></div>
    case 'terminal':
        return <TerminalView isMobile={isMobile} />
      default:
        return null
    }
  })()

  return <ErrorBoundary name={view}>{body}</ErrorBoundary>
}
