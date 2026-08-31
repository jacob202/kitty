import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ResearchView from '../src/components/ResearchView'
import { useActiveProject, useArtifact, useResearchRuns, useStartResearch } from '../src/lib/queries'

vi.mock('../src/lib/queries', () => ({
  useActiveProject: vi.fn(),
  useArtifact: vi.fn(),
  useResearchRuns: vi.fn(),
  useStartResearch: vi.fn(),
}))
vi.mock('../src/components/artifacts/ArtifactCanvas', () => ({
  ArtifactCanvas: ({ artifact, onClose }: any) => <div role="dialog" aria-label={artifact.display_name}>report preview<button onClick={onClose}>close</button></div>,
}))

const completed = {
  id: 'rrun_done', topic: 'battery chemistry', project_id: 7, status: 'completed', stage: 'completed',
  sources: ['https://example.com/a'], summary: 'LFP is stable.', artifact_id: 'artifact_r1', error: null,
  created_at: 100, updated_at: 110, completed_at: 110,
}

describe('ResearchView', () => {
  afterEach(cleanup)

  it('shows live research stages and sources', () => {
    vi.mocked(useActiveProject).mockReturnValue({ data: { project_id: 7, project: { id: 7, name: 'kitty' } } } as never)
    vi.mocked(useStartResearch).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as never)
    vi.mocked(useResearchRuns).mockReturnValue({ data: { runs: [{ ...completed, id: 'rrun_live', status: 'running', stage: 'reading', artifact_id: null }] }, isLoading: false, error: null } as never)
    vi.mocked(useArtifact).mockReturnValue({ data: undefined } as never)

    render(<ResearchView isMobile={false} />)

    expect(screen.getByText('reading')).toBeInTheDocument()
    expect(screen.getByText('battery chemistry')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'example.com' })).toHaveAttribute('href', 'https://example.com/a')
  })

  it('does not turn untrusted source schemes into clickable links', () => {
    vi.mocked(useActiveProject).mockReturnValue({ data: null } as never)
    vi.mocked(useStartResearch).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as never)
    vi.mocked(useResearchRuns).mockReturnValue({ data: { runs: [{ ...completed, sources: ['javascript:alert(1)'] }] }, isLoading: false, error: null } as never)
    vi.mocked(useArtifact).mockReturnValue({ data: undefined } as never)

    render(<ResearchView isMobile={false} />)

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
  })

  it('starts research inside the active project', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ run: { id: 'rrun_new' } })
    vi.mocked(useActiveProject).mockReturnValue({ data: { project_id: 7, project: { id: 7, name: 'kitty' } } } as never)
    vi.mocked(useStartResearch).mockReturnValue({ mutateAsync, isPending: false } as never)
    vi.mocked(useResearchRuns).mockReturnValue({ data: { runs: [] }, isLoading: false, error: null } as never)
    vi.mocked(useArtifact).mockReturnValue({ data: undefined } as never)

    render(<ResearchView isMobile={false} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Research topic' }), { target: { value: 'solid state batteries' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start research' }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ topic: 'solid state batteries', project_id: 7 }))
  })

  it('opens a completed report in the shared artifact canvas', () => {
    vi.mocked(useActiveProject).mockReturnValue({ data: null } as never)
    vi.mocked(useStartResearch).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as never)
    vi.mocked(useResearchRuns).mockReturnValue({ data: { runs: [completed] }, isLoading: false, error: null } as never)
    vi.mocked(useArtifact).mockReturnValue({ data: { id: 'artifact_r1', display_name: 'research.md', media_type: 'text/markdown' } } as never)

    render(<ResearchView isMobile={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open report' }))
    expect(screen.getByRole('dialog', { name: 'research.md' })).toBeInTheDocument()
  })
})
