import { render, screen, within, cleanup } from '@testing-library/react'
import { describe, expect, it, afterEach } from 'vitest'
import { TopBar } from '../src/components/TopBar'
import { MODELS } from '../src/lib/types'

function renderTopBar(isMobile: boolean) {
  return render(
    <TopBar
      activeModel={MODELS[0]}
      models={MODELS}
      onSelectModel={() => {}}
      isStreaming={false}
      activeView="chat"
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

describe('TopBar runtime badge', () => {
  afterEach(cleanup)

  it('desktop shows the runtime label text', () => {
    renderTopBar(false)
    expect(screen.getByText('runtime live')).toBeInTheDocument()
  })

  it('mobile collapses to a dot-only badge that keeps its accessible label', () => {
    renderTopBar(true)
    // The words would wrap the crowded 320px top row — dot only, label via aria.
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

    // Identity row: brand + menu. No project/model controls.
    expect(within(identity).getByText('kitty')).toBeInTheDocument()
    expect(within(identity).getByRole('button', { name: 'Open sidebar' })).toBeInTheDocument()
    expect(within(identity).queryByLabelText('Active project')).not.toBeInTheDocument()
    expect(within(identity).queryByRole('button', { name: /Model:/ })).not.toBeInTheDocument()

    // Workspace row: project selector + model selector, not squeezed next to the brand.
    expect(within(workspace).getByLabelText('Active project')).toBeInTheDocument()
    expect(within(workspace).getByRole('button', { name: /Model:/ })).toBeInTheDocument()
    expect(within(workspace).queryByText('kitty')).not.toBeInTheDocument()
  })
})
