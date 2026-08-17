import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CapturePanel } from '../src/components/CapturePanel'
import { DocumentsPanel } from '../src/components/DocumentsPanel'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return { ...actual, uploadCaptureFile: vi.fn() }
})

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

  it('surfaces capture upload rejection instead of leaking an unhandled promise', async () => {
    vi.mocked(gateway.uploadCaptureFile).mockRejectedValue(new Error('gateway returned 503'))
    const { container } = render(<CapturePanel />)
    const picker = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })

    fireEvent.change(picker, { target: { files: [file] } })

    await waitFor(() => expect(screen.getByText(/upload failed/i)).toBeInTheDocument())
    expect(screen.getByText(/gateway returned 503/i)).toBeInTheDocument()
  })

  it('opens Documents file picker with Space', () => {
    const { container } = render(<DocumentsPanel />)
    const picker = container.querySelector('input[type="file"]') as HTMLInputElement
    const clickPicker = vi.spyOn(picker, 'click')

    fireEvent.keyDown(screen.getByRole('button', { name: /or drop a file here/i }), { key: ' ' })

    expect(clickPicker).toHaveBeenCalledOnce()
  })
})
