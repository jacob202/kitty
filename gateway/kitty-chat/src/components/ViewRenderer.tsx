'use client'

import dynamic from 'next/dynamic'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// -- lazy-loaded view components ------------------------------------------------

const HomeView = dynamic(() => import('./HomeView'))
const ChatView = dynamic(() => import('./ChatView'))
const BuilderView = dynamic(() => import('./BuilderView'))
const SettingsShell = dynamic(() => import('./SettingsShell'))
const WorkView = dynamic(() => import('./WorkView'))
const StudioView = dynamic(() => import('./StudioView'))
const LibraryView = dynamic(() => import('./LibraryView'))
const TutorShell = dynamic(() => import('./TutorShell'))
const TerminalView = dynamic(() => import('./TerminalView'))

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
    onStartClick: () => void
    onChipClick: (chip: string) => void
  }
  homeProps?: {
    preferredName: string
    onDecideInChat: (entry: any) => void
    onNavigate: (view: string) => void
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
        return <HomeView {...homeProps} chatProps={chatProps} compact={isMobile} />
      case 'chat':
        return <ChatView {...chatProps} compact={isMobile} />
      case 'work':
      case 'tasks':
        return <WorkView isMobile={isMobile} />
      case 'studio':
      case 'images':
        return <StudioView isMobile={isMobile} />
      case 'builder':
        return <div style={pad}><BuilderView {...builderProps} /></div>
      case 'library':
      case 'projects':
      case 'docs':
        return <LibraryView isMobile={isMobile} />
    case 'settings':
    case 'providers':
    case 'agents':
    case 'tools':
      return <SettingsShell isMobile={isMobile} theme={(theme as 'cosmic' | 'day' | 'night') ?? 'cosmic'} onToggleTheme={onToggleTheme} />
    case 'tutor':
      return <TutorShell isMobile={isMobile} />
    case 'terminal':
        return <TerminalView isMobile={isMobile} />
      default:
        return null
    }
  })()

  return <ErrorBoundary name={view}>{body}</ErrorBoundary>
}
