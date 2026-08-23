import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ImageLab } from '../src/components/ImageLab'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return { ...actual, useImageStatus: vi.fn() }
})

function onlineStatus() {
  return {
    data: { available: true, engines: [{ name: 'comfyui', label: 'ComfyUI', available: true }] },
    isPending: false, isError: false, isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

function offlineStatus() {
  return {
    data: { available: false, engines: [{ name: 'comfyui', label: 'ComfyUI', available: false }] },
    isPending: false, isError: false, isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

function offlineStatusWithReasons() {
  return {
    data: {
      available: false,
      engines: [
        { name: 'comfyui', label: 'ComfyUI', available: false, unavailable_reason: 'ComfyUI is not running on this Mac. Start ComfyUI, then check again.' },
        { name: 'drawthings', label: 'Draw Things', available: false, unavailable_reason: 'Draw Things is not answering. Open the Draw Things app, turn on its API server, then check again.' },
      ],
    },
    isPending: false, isError: false, isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

function estimate(count = 1) {
  return {
    provider: 'openrouter', model_id: 'vendor/image', recipe_id: 'hosted',
    routing_reason: 'best available', count,
    per_image_estimate: {
      cost: { state: 'known', usd: 0.067, basis: 'observed', samples: 4 },
      duration: { state: 'known', seconds: 12, basis: 'observed', samples: 4 },
    },
    estimate: {
      cost: { state: 'known', usd: 0.067 * count, basis: 'scaled', samples: 4 },
      duration: { state: 'known', seconds: 12 * count, basis: 'scaled', samples: 4 },
    },
  }
}

function queuedBatch(count = 1) {
  return {
    batch_id: 'imgbatch_1', session_id: 'imgses_1', status: 'queued', count,
    estimate: estimate(count).estimate,
    request: { prompt: 'portrait' },
    items: Array.from({ length: count }, (_, ordinal) => ({
      item_id: `item_${ordinal}`, ordinal, status: 'queued', job_id: null, result: null, error: null,
    })),
  }
}

function stubFetch() {
  const mock = vi.fn(async (url: string, init?: RequestInit) => {
    const target = String(url)
    const method = init?.method ?? 'GET'
    if (target === '/proxy/studio/estimate') {
      const count = JSON.parse(String(init?.body ?? '{}')).count ?? 1
      return { ok: true, status: 200, json: async () => estimate(count) }
    }
    if (target === '/proxy/studio/sessions' && method === 'POST') {
      return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', turns: [], jobs: [] }) }
    }
    if (target === '/proxy/studio/agent') {
      return { ok: true, status: 200, json: async () => ({
        action: 'generate', session_id: 'imgses_1', summary: 'Rendering four portrait options.',
        plan_id: 'imgplan_1', plan: null, operation: 'txt2img', anchor_job_id: null,
        protected_traits: [], requested_changes: [], question: null, reason: null,
      }) }
    }
    if (target === '/proxy/studio/batches' && method === 'POST') {
      const count = JSON.parse(String(init?.body ?? '{}')).count ?? 1
      return { ok: true, status: 200, json: async () => queuedBatch(count) }
    }
    if (target.startsWith('/proxy/studio/batches?')) {
      return { ok: true, status: 200, json: async () => ({ batches: [] }) }
    }
    if (target === '/proxy/studio/batches/imgbatch_1') {
      return { ok: true, status: 200, json: async () => queuedBatch(4) }
    }
    if (target.startsWith('/proxy/studio/sessions/')) {
      return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', turns: [], jobs: [] }) }
    }
    return { ok: true, status: 200, json: async () => ({}) }
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

describe('ImageLab', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.mocked(queries.useImageStatus).mockReturnValue(onlineStatus() as never)
  })
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  it('shows the total estimate and queues one durable 4-image batch', async () => {
    const fetchMock = stubFetch()
    render(<ImageLab />)

    fireEvent.click(screen.getByRole('button', { name: '4 images' }))
    const estimateLine = await screen.findByTestId('image-lab-estimate')
    await waitFor(() => expect(estimateLine).toHaveTextContent('$0.27'))
    expect(estimateLine).toHaveTextContent('~48 sec')

    const input = screen.getByPlaceholderText(/tell kitty what you want to make/i)
    fireEvent.change(input, { target: { value: 'portrait' } })
    fireEvent.click(screen.getByTestId('image-lab-send'))

    await waitFor(() => expect(screen.getByText(/Rendering four portrait options/i)).toBeInTheDocument())
    const batchCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === '/proxy/studio/batches' && (init as RequestInit | undefined)?.method === 'POST'
    )
    expect(batchCall).toBeTruthy()
    expect(JSON.parse(String((batchCall?.[1] as RequestInit).body))).toMatchObject({
      count: 4, plan_id: 'imgplan_1', session_id: 'imgses_1', prompt: 'portrait',
    })
    expect(screen.getByText(/4 images queued/i)).toBeInTheDocument()
  })

  it('reattaches to a persisted session and its queued work after reload', async () => {
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_1')
    const batch = queuedBatch(2)
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const target = String(url)
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate(1) }
      if (target === '/proxy/studio/sessions/imgses_1') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', turns: [], jobs: [] }) }
      if (target.startsWith('/proxy/studio/batches?')) return { ok: true, status: 200, json: async () => ({ batches: [batch] }) }
      if (target === `/proxy/studio/batches/${batch.batch_id}`) return { ok: true, status: 200, json: async () => batch }
      return { ok: true, status: 200, json: async () => ({}) }
    }))

    render(<ImageLab />)
    await waitFor(() => expect(screen.getByText(/2 images queued/i)).toBeInTheDocument())
    expect(window.localStorage.getItem('kitty-image-lab-session')).toBe('imgses_1')
  })

  it('keeps the conversational workspace usable while generation is offline', async () => {
    vi.mocked(queries.useImageStatus).mockReturnValue(offlineStatus() as never)
    stubFetch()
    render(<ImageLab />)

    expect(await screen.findByText(/no image engine is online/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/tell kitty what you want to make/i)).toBeInTheDocument()
    expect(screen.getByTestId('image-lab-send')).toBeDisabled()
  })

  it('tells the user how to bring an offline engine back', async () => {
    vi.mocked(queries.useImageStatus).mockReturnValue(offlineStatusWithReasons() as never)
    stubFetch()
    render(<ImageLab />)

    expect(await screen.findByText(/no image engine is online/i)).toBeInTheDocument()
    expect(screen.getByText(/Start ComfyUI, then check again/i)).toBeInTheDocument()
    expect(screen.getByText(/Open the Draw Things app/i)).toBeInTheDocument()
  })

  it('carries a picked character into a freshly created session', async () => {
    const charactersPayload = {
      characters: [{
        character_id: 'char_1', name: 'Mia', description: null, identity_preset: 'balanced',
        references: [{ ref_id: 'ref_1', is_primary: true, original_name: 'mia.png', storage_path: 'imgrefs/mia.png' }],
      }],
    }
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      const method = init?.method ?? 'GET'
      if (target === '/proxy/studio/estimate') {
        const count = JSON.parse(String(init?.body ?? '{}')).count ?? 1
        return { ok: true, status: 200, json: async () => estimate(count) }
      }
      if (target === '/proxy/studio/characters' && method === 'GET') {
        return { ok: true, status: 200, json: async () => charactersPayload }
      }
      if (target === '/proxy/studio/sessions' && method === 'POST') {
        return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', character_id: 'char_1', turns: [], jobs: [] }) }
      }
      if (target === '/proxy/studio/agent') {
        return { ok: true, status: 200, json: async () => ({
          action: 'generate', session_id: 'imgses_1', summary: 'Rendering Mia with her reference locked in.',
          plan_id: 'imgplan_1', plan: null, operation: 'txt2img', anchor_job_id: null,
          protected_traits: [], requested_changes: [], question: null, reason: null,
        }) }
      }
      if (target === '/proxy/studio/batches' && method === 'POST') {
        const count = JSON.parse(String(init?.body ?? '{}')).count ?? 1
        return { ok: true, status: 200, json: async () => queuedBatch(count) }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    fireEvent.click(await screen.findByTestId('image-lab-character-picker'))
    fireEvent.click(screen.getByText('Mia'))

    await waitFor(() => {
      const characterEstimateCall = fetchMock.mock.calls.find(([url, init]) => {
        if (String(url) !== '/proxy/studio/estimate') return false
        const body = JSON.parse(String((init as RequestInit | undefined)?.body ?? '{}'))
        return body.character_id === 'char_1'
      })
      expect(characterEstimateCall).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/tell kitty what you want to make/i)
    fireEvent.change(input, { target: { value: 'portrait of Mia' } })
    fireEvent.click(screen.getByTestId('image-lab-send'))

    await waitFor(() => expect(screen.getByText(/Rendering Mia with her reference locked in/i)).toBeInTheDocument())
    const sessionCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === '/proxy/studio/sessions' && (init as RequestInit | undefined)?.method === 'POST'
    )
    expect(sessionCall).toBeTruthy()
    expect(JSON.parse(String((sessionCall?.[1] as RequestInit).body))).toEqual({ character_id: 'char_1' })

    const batchCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === '/proxy/studio/batches' && (init as RequestInit | undefined)?.method === 'POST'
    )
    expect(batchCall).toBeTruthy()
    expect(JSON.parse(String((batchCall?.[1] as RequestInit).body))).toMatchObject({
      character_id: 'char_1', plan_id: 'imgplan_1', session_id: 'imgses_1',
    })
  })

  it('binds a character to the persisted session over PATCH', async () => {
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_1')
    const charactersPayload = {
      characters: [{ character_id: 'char_1', name: 'Mia', description: null, identity_preset: 'balanced', references: [] }],
    }
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      const method = init?.method ?? 'GET'
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate(1) }
      if (target === '/proxy/studio/characters' && method === 'GET') {
        return { ok: true, status: 200, json: async () => charactersPayload }
      }
      if (target === '/proxy/studio/sessions/imgses_1' && method === 'GET') {
        return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', anchor_job_id: null, turns: [], jobs: [] }) }
      }
      if (target.startsWith('/proxy/studio/batches?')) {
        return { ok: true, status: 200, json: async () => ({ batches: [] }) }
      }
      if (target === '/proxy/studio/sessions/imgses_1' && method === 'PATCH') {
        return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', character_id: 'char_1', turns: [], jobs: [] }) }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    fireEvent.click(await screen.findByTestId('image-lab-character-picker'))
    fireEvent.click(screen.getByText('Mia'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/proxy/studio/sessions/imgses_1', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character_id: 'char_1' }),
      })
    })
  })
})
