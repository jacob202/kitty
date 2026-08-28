import { render, screen, within, cleanup } from '@testing-library/react'
import { describe, expect, it, afterEach } from 'vitest'
import { TopBar } from '../src/components/TopBar'
import { MODELS } from '../src/lib/types'

function renderTopBar(isMobile: boolean, activeView = 'chat') {
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
      runtimeState="available"
      onToggleSidebar={() => {}}
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
})

describe('TopBar runtime badge', () => {
  afterEach(cleanup)

  it('desktop shows the runtime label text', () => {
    renderTopBar(false)
    expect(screen.getByText('runtime live')).toBeInTheDocument()
  })

  it('mobile collapses to a dot-only badge that keeps its accessible label', () => {
    renderTopBar(true)
    expect(screen.queryByText('runtime live')).not.toBeInTheDocument()
    expect(screen.getByLabelText('runtime live')).toBeInTheDocument()
  })
})

describe('TopBar mobile two-row header (#346)', () => {
  afterEach(cleanup)
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
