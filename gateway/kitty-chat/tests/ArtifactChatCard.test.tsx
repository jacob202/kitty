import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ArtifactChatCard } from '../src/components/chat/ArtifactChatCard'
import { useArtifact } from '../src/lib/queries'

vi.mock('../src/lib/queries', () => ({ useArtifact: vi.fn() }))
vi.mock('../src/components/artifacts/ArtifactCanvas', () => ({
  canPreviewArtifact: () => true,
  ArtifactCanvas: ({ artifact, onClose }: { artifact: { display_name: string }; onClose: () => void }) => (
    <div role="dialog" aria-label={artifact.display_name}>
      previewing {artifact.display_name}
      <button onClick={onClose}>close preview</button>
    </div>
  ),
}))

const artifact = {
  id: 'artifact_1', project_id: 7, kind: 'document', media_type: 'text/markdown',
  display_name: 'research-report.md', state: 'ready', size_bytes: 2048,
  created_at: 1787259000, created_by: 'research', metadata: {}, error: null,
}

describe('ArtifactChatCard', () => {
  afterEach(cleanup)

  it('renders durable artifact metadata and opens the shared canvas', () => {
    vi.mocked(useArtifact).mockReturnValue({ data: artifact, isLoading: false, isError: false } as never)
    render(<ArtifactChatCard artifactId="artifact_1" isMobile={false} />)

    expect(screen.getByText('research-report.md')).toBeInTheDocument()
    expect(screen.getByText(/document/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open artifact' }))
    expect(screen.getByRole('dialog', { name: 'research-report.md' })).toBeInTheDocument()
  })

  it('shows the recorded failure reason for failed artifacts', () => {
    vi.mocked(useArtifact).mockReturnValue({
      data: { ...artifact, state: 'failed', error: 'PDF conversion failed' },
      isLoading: false, isError: false,
    } as never)
    render(<ArtifactChatCard artifactId="artifact_1" isMobile={false} />)

    expect(screen.getByRole('alert')).toHaveTextContent('PDF conversion failed')
    expect(screen.queryByText(/Preview unavailable/i)).not.toBeInTheDocument()
  })

})
