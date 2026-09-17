import { act, cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { KittyProvider, useKitty } from '../src/state/KittyContext'

// Reproduces: staged attachments live in one global `attachments` state, not
// scoped per chat, and handleSelectChat never clears them on switch. A file
// uploaded while chat A is active (already bound server-side to chat A's
// conversation_id via uploadCaptureFile) can get silently sent attached to a
// message in whatever chat is active when handleSend next fires.

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))

const query = (data: unknown = undefined) => ({
  data,
  isFetched: true,
  isSuccess: false,
  isLoading: false,
  isPending: false,
  isError: false,
  error: null,
})

vi.mock('../src/lib/queries', () => ({
  useGatewayBrief: () => query({ fromLiveGateway: true }),
  useGatewayModels: () => query({ models: [], fromLiveGateway: false }),
  useGatewayRuntimeManifest: () => query(),
  useProviders: () => query({ active: 'auto', order: [], providers: [], warnings: [], config_path: 'test' }),
  useActiveProject: () => query({ project: null }),
  useProjects: () => query([]),
  useSetActiveProject: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useLoops: () => query({ loops: [] }),
  useInsights: () => query({ insights: [] }),
  usePrompts: () => query([]),
  useToggleLoop: () => ({ mutate: vi.fn() }),
  useDismissInsight: () => ({ mutate: vi.fn() }),
  hasActiveBuilderRun: () => false,
}))

vi.mock('../src/hooks/useKittyState', () => ({ useKittyState: () => 'idle' }))
vi.mock('../src/lib/pwa', () => ({
  usePwaInstall: () => ({ state: 'unsupported', error: null, installing: false, install: vi.fn() }),
}))

const uploadCaptureFile = vi.fn()
vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof import('../src/lib/gateway')>('../src/lib/gateway')
  return { ...actual, uploadCaptureFile: (...args: unknown[]) => uploadCaptureFile(...args) }
})

let kittyRef: ReturnType<typeof useKitty> | null = null
function Harness() {
  const kitty = useKitty()
  kittyRef = kitty
  return <div data-testid="active-chat">{kitty.activeChat?.id ?? ''}</div>
}

function mountHarness() {
  return render(<KittyProvider><Harness /></KittyProvider>)
}

describe('attachment staging is scoped to the chat it was uploaded for', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem('kitty-onboarded', 'true')
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false, media: query, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
      })),
    })
    uploadCaptureFile.mockReset()
  })

  afterEach(() => cleanup())

  it('does not carry an attachment uploaded for chat A into chat B after switching', async () => {
    mountHarness()
    await waitFor(() => expect(kittyRef).not.toBeNull())

    const chatAId = kittyRef!.activeChat!.id

    uploadCaptureFile.mockResolvedValue({ artifact_id: 'art-1' })
    const file = new File(['x'], 'note.txt', { type: 'text/plain' })
    const fileList = { 0: file, length: 1, item: (i: number) => (i === 0 ? file : null) } as unknown as FileList

    await act(async () => {
      await kittyRef!.handleAddFiles(fileList)
    })

    // Confirm the upload was bound to chat A server-side.
    expect(uploadCaptureFile).toHaveBeenCalledWith(
      file,
      expect.objectContaining({ conversationId: chatAId }),
    )
    expect(kittyRef!.attachments).toHaveLength(1)

    act(() => {
      kittyRef!.handleNewChat()
    })
    await waitFor(() => expect(kittyRef!.activeChat!.id).not.toBe(chatAId))

    // This is the bug: switching chats should clear (or at least not carry
    // forward) attachments staged for a different chat's conversation_id.
    expect(kittyRef!.attachments).toHaveLength(0)
  })
})
