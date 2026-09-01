import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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

  it('moves keyboard focus into the canvas when it opens', () => {
    render(<ArtifactCanvas artifact={artifact()} isMobile={false} onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Close artifact' })).toHaveFocus()
  })

  it('uses the full viewport width on mobile and closes on Escape', () => {
    const onClose = vi.fn()
    render(<ArtifactCanvas artifact={artifact()} isMobile onClose={onClose} />)

    expect(screen.getByRole('dialog', { name: 'reference.png' })).toHaveStyle({ width: '100%' })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
