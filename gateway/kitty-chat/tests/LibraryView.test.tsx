import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LibraryView from '../src/components/LibraryView'

const setAttachments = vi.fn()
const setActiveView = vi.fn()

vi.mock('../src/state/KittyContext', () => ({
  useKitty: () => ({ setAttachments, setActiveView }),
}))

vi.mock('../src/components/DocumentsPanel', () => ({
  DocumentsPanel: () => <div>knowledge unavailable — retry indexing</div>,
}))

function renderLibrary(isMobile = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <LibraryView isMobile={isMobile} />
    </QueryClientProvider>,
  )
}

describe('LibraryView artifact truth', () => {
  beforeEach(() => {
    setAttachments.mockReset()
    setActiveView.mockReset()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/proxy/artifacts')) {
        return new Response(JSON.stringify({
          artifacts: [{
            id: 'artifact_1',
            project_id: 7,
            kind: 'capture',
            media_type: 'image/png',
            display_name: 'camera-reference.png',
            state: 'ready',
            size_bytes: 2048,
            created_at: 1787259000,
            created_by: 'capture',
            conversation_id: 'chat-1',
            metadata: { ingestion_status: 'queued' },
            error: null,
          }],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('not found', { status: 404 })
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('shows canonical artifacts even when the knowledge index is degraded', async () => {
    renderLibrary()

    expect(await screen.findByText('camera-reference.png')).toBeInTheDocument()
    expect(screen.getByText(/image\/png/i)).toBeInTheDocument()
    expect(screen.getByText(/project 7/i)).toBeInTheDocument()
    expect(screen.getByText(/conversation chat-1/i)).toBeInTheDocument()
    expect(screen.getByText(/knowledge unavailable/i)).toBeInTheDocument()
  })



  it('prioritizes recent artifacts with readable state and secondary technical details', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      artifacts: [
        {
          id: 'artifact_old', project_id: 7, kind: 'document', media_type: 'application/pdf',
          display_name: 'older-notes.pdf', state: 'ready', size_bytes: 4096, created_at: 1787250000,
          created_by: 'capture', conversation_id: 'chat-old', metadata: { ingestion_status: 'success' }, error: null,
        },
        {
          id: 'artifact_new', project_id: 8, kind: 'capture', media_type: 'image/png',
          display_name: 'new-camera-reference.png', state: 'processing', size_bytes: 2048, created_at: 1787259000,
          created_by: 'capture', conversation_id: 'chat-new', metadata: { ingestion_status: 'queued' }, error: null,
        },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    renderLibrary()

    const list = await screen.findByRole('list', { name: /recent artifacts/i })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByText('new-camera-reference.png')).toBeInTheDocument()
    expect(within(items[0]).getByText('Image')).toBeInTheDocument()
    expect(within(items[0]).getByText('Processing')).toBeInTheDocument()
    const details = within(items[0]).getByText(/details/i).closest('details')
    expect(details).not.toBeNull()
    expect(within(details as HTMLElement).getByText(/project 8/i)).toBeInTheDocument()
    expect(within(details as HTMLElement).getByText(/conversation chat-new/i)).toBeInTheDocument()
  })

  it('stages a ready image into chat and switches to the chat view', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/proxy/artifacts')) {
        return new Response(JSON.stringify({
          artifacts: [{
            id: 'artifact_1', project_id: 7, kind: 'capture', media_type: 'image/png',
            display_name: 'camera-reference.png', state: 'ready', size_bytes: 2048,
            created_at: 1787259000, created_by: 'capture', conversation_id: 'chat-1',
            metadata: { ingestion_status: 'queued' }, error: null,
          }],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/proxy/chats/use-in-chat')) {
        return new Response(JSON.stringify({
          id: 'artifact_1', display_name: 'camera-reference.png',
          media_type: 'image/png', size: 2048, data_url: 'data:image/png;base64,AAAA',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('not found', { status: 404 })
    }))

    renderLibrary()

    const action = await screen.findByRole('button', { name: /use camera-reference\.png in chat/i })
    expect(action).toBeEnabled()
    fireEvent.click(action)

    expect(await screen.findByText('camera-reference.png')).toBeInTheDocument()
    expect(setAttachments).toHaveBeenCalled()
    expect(setActiveView).toHaveBeenCalledWith('chat')
  })

  it('shows the gateway plain-language reason when an artifact cannot be used in chat', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/proxy/artifacts')) {
        return new Response(JSON.stringify({
          artifacts: [{
            id: 'artifact_pdf', project_id: 7, kind: 'document', media_type: 'application/pdf',
            display_name: 'notes.pdf', state: 'ready', size_bytes: 4096,
            created_at: 1787259000, created_by: 'capture', conversation_id: 'chat-1',
            metadata: {}, error: null,
          }],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/proxy/chats/use-in-chat')) {
        return new Response(JSON.stringify({ detail: 'Only images can be attached into a chat message from Library.' }), { status: 415, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('not found', { status: 404 })
    }))

    renderLibrary()

    const action = await screen.findByRole('button', { name: /use notes\.pdf in chat/i })
    expect(action).toBeEnabled()
    fireEvent.click(action)

    expect(await screen.findByRole('alert')).toHaveTextContent(/Only images can be attached into a chat message/)
    expect(setAttachments).not.toHaveBeenCalled()
    expect(setActiveView).not.toHaveBeenCalled()
  })

  it('keeps the disabled-use control for non-image or non-ready artifacts with a plain reason', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      artifacts: [
        {
          id: 'artifact_pdf', project_id: 7, kind: 'document', media_type: 'application/pdf',
          display_name: 'notes.pdf', state: 'ready', size_bytes: 4096, created_at: 1787250000,
          created_by: 'capture', conversation_id: 'chat-old', metadata: {}, error: null,
        },
        {
          id: 'artifact_processing', project_id: 8, kind: 'capture', media_type: 'image/png',
          display_name: 'new-camera-reference.png', state: 'processing', size_bytes: 2048, created_at: 1787259000,
          created_by: 'capture', conversation_id: 'chat-new', metadata: { ingestion_status: 'queued' }, error: null,
        },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    renderLibrary()

    const pdf = await screen.findByRole('button', { name: /use notes\.pdf in chat unavailable/i })
    expect(pdf).toBeDisabled()
    expect(screen.getByText(/only images can be attached/i)).toBeInTheDocument()

    const processing = screen.getByRole('button', { name: /use new-camera-reference\.png in chat unavailable/i })
    expect(processing).toBeDisabled()
    expect(screen.getByText(/not ready to use in chat yet/i)).toBeInTheDocument()
    expect(setAttachments).not.toHaveBeenCalled()
    expect(setActiveView).not.toHaveBeenCalled()
  })

  it('keeps important Library controls at least 44px tall on mobile', async () => {
    renderLibrary(true)

    const refresh = await screen.findByRole('button', { name: /refresh artifacts/i })
    expect(refresh).toHaveStyle({ minHeight: '44px' })
  })

  it('fails closed when the artifact endpoint returns malformed success data', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ artifacts: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })))
    renderLibrary()

    expect(await screen.findByText(/saved files returned an invalid response/i)).toBeInTheDocument()
    expect(screen.getByText(/knowledge unavailable/i)).toBeInTheDocument()
  })

  it('keeps raw gateway auth errors out of the primary recovery message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('unauthorized', { status: 401, statusText: 'Unauthorized' })))
    renderLibrary()

    expect(await screen.findByText(/Kitty wouldn't allow that request/i)).toBeInTheDocument()
    expect(screen.queryByText(/Gateway returned 401/i)).not.toBeInTheDocument()
    // The advice must not name a control that does not exist in Settings.
    expect(screen.queryByText(/gateway secret/i)).not.toBeInTheDocument()
  })

  it('keeps the knowledge index visible when artifact listing fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('offline', { status: 503 })))
    renderLibrary()

    expect(await screen.findByText(/couldn't read saved files/i)).toBeInTheDocument()
    expect(screen.getByText(/knowledge unavailable/i)).toBeInTheDocument()
  })
})
