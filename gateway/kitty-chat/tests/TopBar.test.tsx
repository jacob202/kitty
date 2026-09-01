import { render, screen, within, cleanup } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'
import { TopBar } from '../src/components/TopBar'
import { MODELS } from '../src/lib/types'

function renderTopBar(
  isMobile: boolean,
  activeView = 'chat',
  runtimeState: 'available' | 'unavailable' | 'degraded' | 'stale' | 'unknown' = 'available',
  onActivity?: () => void,
  activityAttentionCount = 0,
  activityIncomplete = false,
) {
  return render(
    <TopBar
      activeModel={MODELS[0]}
      models={MODELS}
      onSelectModel={() => {}}
      isStreaming={false}
      activeView={activeView}
      onViewChange={() => {}}
      kittyMode="default"
      onKittyModeChange={() => {}}
      isMobile={isMobile}
      runtimeState={runtimeState}
      onActivity={onActivity}
      activityAttentionCount={activityAttentionCount}
      activityIncomplete={activityIncomplete}
      onToggleSidebar={() => {}}
      onCommandPalette={() => {}}
      onSelectProject={() => {}}
      activeProject={{ id: 1, name: 'kitty-gateway-rebuild' }}
      projects={[{ id: 1, name: 'kitty-gateway-rebuild' }]}
    />,
  )
}

describe('TopBar surface hierarchy', () => {
  afterEach(cleanup)
  it('names the active desktop surface instead of repeating the product brand', () => {
    renderTopBar(false, 'projects')
    const toolbar = screen.getByRole('banner', { name: 'Workspace toolbar' })
    expect(within(toolbar).getByText('Projects')).toBeInTheDocument()
    expect(within(toolbar).queryByRole('heading')).not.toBeInTheDocument()
    expect(screen.queryByText('kitty')).not.toBeInTheDocument()
  })

  it('uses the product-facing Image Lab name for the studio route', () => {
    renderTopBar(false, 'studio')
    const toolbar = screen.getByRole('banner', { name: 'Workspace toolbar' })
    expect(within(toolbar).getByText('Image Lab')).toBeInTheDocument()
    expect(within(toolbar).queryByRole('heading')).not.toBeInTheDocument()
  })

  it('shows Tasks label for the tasks view', () => {
    renderTopBar(false, 'tasks')
    const toolbar = screen.getByRole('banner', { name: 'Workspace toolbar' })
    expect(within(toolbar).getByText('Tasks')).toBeInTheDocument()
    expect(within(toolbar).queryByRole('heading')).not.toBeInTheDocument()
    expect(screen.queryByText('kitty')).not.toBeInTheDocument()
  })
})

describe('TopBar activity entry point', () => {
  afterEach(cleanup)

  it('shows incomplete status instead of presenting partial counts as complete', () => {
    renderTopBar(false, 'chat', 'available', vi.fn(), 3, true)
    const button = screen.getByRole('button', { name: /activity.*incomplete.*3 known/i })
    expect(button).toHaveTextContent('Activity')
    expect(button).toHaveTextContent('?')
  })

  it('shows the attention count and opens the global activity surface', () => {
    const onActivity = vi.fn()
    renderTopBar(false, 'chat', 'available', onActivity, 3)

    const button = screen.getByRole('button', { name: 'Open activity, 3 need attention' })
    expect(button).toHaveTextContent('Activity')
    expect(button).toHaveTextContent('3')
    button.click()
    expect(onActivity).toHaveBeenCalledTimes(1)
  })
})

describe('TopBar runtime badge', () => {
  afterEach(cleanup)

  it('desktop shows the runtime label text', () => {
    renderTopBar(false)
    expect(screen.getByText('connected')).toBeInTheDocument()
  })

  it('labels an idle task state without claiming the whole product is ready', () => {
    renderTopBar(false, 'chat', 'available')
    expect(screen.getByText('idle')).toBeInTheDocument()
    expect(screen.queryByText('ready')).not.toBeInTheDocument()
  })

  it('mobile collapses to a dot-only badge that keeps its accessible label', () => {
    renderTopBar(true)
    expect(screen.queryByText('connected')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Connection to Kitty: connected')).toBeInTheDocument()
  })

  // The badge sits right next to the cat StateBadge, which reports Kitty's
  // own state (e.g. "idle"). Wording that starts with "Kitty ___" here read
  // as a second, contradictory claim about the same thing — the
  // label must unambiguously describe the backend connection instead.
  it('does not claim ready while the backend is unavailable', () => {
    renderTopBar(true, 'chat', 'unavailable')
    expect(screen.queryByText('ready')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Connection to Kitty: not connected')).toBeInTheDocument()
  })

  it('does not claim ready while the backend state is unknown', () => {
    renderTopBar(false, 'chat', 'unknown')
    expect(screen.queryByText('ready')).not.toBeInTheDocument()
    expect(screen.getByText('connection unknown')).toBeInTheDocument()
  })

  it('describes the backend connection, not Kitty itself, when unavailable', () => {
    renderTopBar(false, 'chat', 'unavailable')
    expect(screen.getByText('not connected')).toBeInTheDocument()
    expect(screen.queryByText(/^Kitty /)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Connection to Kitty: not connected')).toBeInTheDocument()
  })

  it('describes the backend connection, not Kitty itself, when unknown', () => {
    renderTopBar(false, 'chat', 'unknown')
    expect(screen.getByText('connection unknown')).toBeInTheDocument()
    expect(screen.queryByText(/^Kitty /)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Connection to Kitty is unknown')).toBeInTheDocument()
  })
})

describe('TopBar mobile two-row header (#346)', () => {
  afterEach(cleanup)
  it('keeps the capability launcher reachable on touch layouts', () => {
    renderTopBar(true)
    expect(screen.getByRole('button', { name: 'Open command palette' })).toBeInTheDocument()
  })

  it('moves the workspace and model controls out of the cramped identity row', () => {
    renderTopBar(true)

    const identity = screen.getByTestId('topbar-identity-row')
    const workspace = screen.getByTestId('topbar-workspace-row')

    expect(within(identity).getByText('kitty')).toBeInTheDocument()
    expect(within(identity).getByRole('button', { name: 'Open sidebar' })).toBeInTheDocument()
    expect(within(identity).queryByLabelText('Active project')).not.toBeInTheDocument()
    expect(within(identity).queryByRole('button', { name: /Model:/ })).not.toBeInTheDocument()

    expect(within(workspace).getByLabelText('Active project')).toBeInTheDocument()
    expect(within(workspace).getByRole('button', { name: /Model:/ })).toBeInTheDocument()
    expect(within(workspace).queryByText('kitty')).not.toBeInTheDocument()
  })
})
