import { render, screen, cleanup } from '@testing-library/react'
import { describe, expect, it, afterEach } from 'vitest'
import { TopBar } from '../src/components/TopBar'
import { MODELS } from '../src/lib/types'

function renderTopBar(isMobile: boolean) {
  return render(
    <TopBar
      activeModel={MODELS[0]}
      models={MODELS}
      onSelectModel={() => {}}
      showModelMenu={false}
      setShowModelMenu={() => {}}
      isStreaming={false}
      activeChat={null}
      activeView="chat"
      onViewChange={() => {}}
      kittyMode="default"
      onKittyModeChange={() => {}}
      isMobile={isMobile}
      runtimeState="available"
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
