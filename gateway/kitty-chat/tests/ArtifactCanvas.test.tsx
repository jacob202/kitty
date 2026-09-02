import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ArtifactCanvas, canPreviewArtifact } from '../src/components/artifacts/ArtifactCanvas'
import type { GatewayArtifact } from '../src/lib/gateway'

function artifact(overrides: Partial<GatewayArtifact> = {}): GatewayArtifact {
  return {
    id: 'artifact/image one',
    project_id: null,
    kind: 'document',
    media_type: 'image/png',
    display_name: 'reference.png',
    state: 'ready',
    size_bytes: 2048,
    created_at: 1,
    created_by: 'test',
    metadata: {},
    ...overrides,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  cleanup()
})

describe('ArtifactCanvas', () => {
  it('allows only ready passive preview media', () => {
    expect(canPreviewArtifact(artifact())).toBe(true)
    expect(canPreviewArtifact(artifact({ media_type: 'application/pdf' }))).toBe(true)
    expect(canPreviewArtifact(artifact({ media_type: 'text/markdown' }))).toBe(true)
    expect(canPreviewArtifact(artifact({ media_type: 'text/html' }))).toBe(false)
    expect(canPreviewArtifact(artifact({ state: 'processing' }))).toBe(false)
  })

  it('renders an image through the artifact-id content route', () => {
    render(<ArtifactCanvas artifact={artifact()} isMobile={false} onClose={vi.fn()} />)

    const image = screen.getByRole('img', { name: 'reference.png' })
    expect(image).toHaveAttribute('src', '/proxy/artifacts/artifact%2Fimage%20one/content')
    expect(screen.queryByText('artifact', { exact: true })).not.toBeInTheDocument()
  })

  it('renders a PDF inline through the artifact-id content route', () => {
    render(<ArtifactCanvas artifact={artifact({ media_type: 'application/pdf', display_name: 'report.pdf' })} isMobile={false} onClose={vi.fn()} />)

    const frame = screen.getByTitle('Preview report.pdf')
    expect(frame).toHaveAttribute('src', '/proxy/artifacts/artifact%2Fimage%20one/content')
  })


  it('moves focus into the canvas and restores it after close', () => {
    const trigger = document.createElement('button')
    trigger.textContent = 'Open artifact'
    document.body.appendChild(trigger)
    trigger.focus()

    const view = render(<ArtifactCanvas artifact={artifact()} isMobile={false} onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: /close artifact/i })).toHaveFocus()

    view.unmount()
    expect(trigger).toHaveFocus()
    trigger.remove()
  })

  it('shows image load failures instead of a broken image placeholder', async () => {
    render(<ArtifactCanvas artifact={artifact()} isMobile={false} onClose={vi.fn()} />)
    fireEvent.error(screen.getByRole('img', { name: 'reference.png' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be loaded/i)
  })

  it('does not automatically load remote images embedded in Markdown', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('![tracking pixel](https://example.test/pixel.png)', { status: 200 })))
    render(<ArtifactCanvas artifact={artifact({ media_type: 'text/markdown', display_name: 'notes.md' })} isMobile={false} onClose={vi.fn()} />)

    expect(await screen.findByText(/remote image blocked/i)).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /tracking pixel/i })).not.toBeInTheDocument()
  })

  it('reserves the mobile bottom safe area for actions', () => {
    render(<ArtifactCanvas artifact={artifact()} isMobile onClose={vi.fn()} onUseInChat={vi.fn()} />)
    const action = screen.getByRole('button', { name: /use in chat/i })
    expect(action.parentElement?.getAttribute('style')).toContain('safe-area-inset-bottom')
  })

  it('uses the full viewport width on mobile and closes on Escape', () => {
    const onClose = vi.fn()
    render(<ArtifactCanvas artifact={artifact()} isMobile onClose={onClose} />)

    expect(screen.getByRole('dialog', { name: 'reference.png' })).toHaveStyle({ width: '100%' })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
