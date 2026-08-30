import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CapturePanel } from '../src/components/CapturePanel'
import { DocumentsPanel } from '../src/components/DocumentsPanel'

vi.mock('../src/lib/queries', () => ({
  useKnowledgeSources: () => ({ data: undefined, isLoading: false, isError: false, isFetching: false, refetch: vi.fn() }),
  useKnowledgeSearch: () => ({ data: undefined, isLoading: false, isError: false }),
  useIngestKnowledge: () => ({ isPending: false, isError: false, mutate: vi.fn() }),
  useUploadCapture: () => ({ isPending: false, isError: false, isSuccess: false, data: undefined, mutate: vi.fn() }),
}))

describe('file drop zones', () => {
  afterEach(cleanup)

  it.each(['Enter', ' '])('opens Capture file picker with %s', (key) => {
    const { container } = render(<CapturePanel />)
    const picker = container.querySelector('input[type="file"]') as HTMLInputElement
    const clickPicker = vi.spyOn(picker, 'click')

    const dropZone = screen.getByRole('button', { name: /drop file or click to capture/i })
    expect(dropZone).toHaveAttribute('tabindex', '0')
    fireEvent.keyDown(dropZone, { key })

    expect(clickPicker).toHaveBeenCalledOnce()
  })

  it('opens Documents file picker with Space', () => {
    const { container } = render(<DocumentsPanel />)
    const picker = container.querySelector('input[type="file"]') as HTMLInputElement
    const clickPicker = vi.spyOn(picker, 'click')

    fireEvent.keyDown(screen.getByRole('button', { name: /or drop a file here/i }), { key: ' ' })

    expect(clickPicker).toHaveBeenCalledOnce()
  })
})
