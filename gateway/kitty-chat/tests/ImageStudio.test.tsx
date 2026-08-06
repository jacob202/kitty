import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest'
import { ImageStudio } from '../src/components/ImageStudio'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useImageStatus: vi.fn(),
  }
})

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const view = render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
  return { ...view, client }
}

function offlineStatus() {
  return {
    data: {
      available: false,
      backend: 'comfyui',
      engines: [
        { name: 'comfyui', label: 'ComfyUI', available: false },
        { name: 'drawthings', label: 'Draw Things', available: false },
      ],
    },
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

function errorStatus() {
  // Gateway / image-status endpoint unreachable — a DIFFERENT failure than
  // renderers being offline (PR #355 review finding 2).
  return {
    data: undefined,
    isPending: false,
    isError: true,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    error: new Error('Gateway returned 503 Service Unavailable'),
  }
}

function onlineStatus() {
  return {
    data: {
      available: true,
      backend: 'comfyui',
      engines: [{ name: 'comfyui', label: 'ComfyUI', available: true }],
    },
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

<<<<<<< HEAD
=======
function agentDecision(overrides: Record<string, unknown> = {}) {
  return {
    action: 'generate',
    session_id: 'imgses_1',
    summary: 'Rendering a golden-hour portrait.',
    plan_id: 'imgplan_1',
    plan: null,
    operation: 'txt2img',
    anchor_job_id: null,
    protected_traits: [],
    requested_changes: [],
    question: null,
    reason: null,
    ...overrides,
  }
}

>>>>>>> origin/main
/** Stub global fetch for Studio routes; route generation to a raw HTML error to
 *  exercise finding 4. */
function stubStudioFetch(generateResponse?: unknown) {
  const mock = vi.fn(async (url: string, _init?: unknown) => {
    if (String(url).includes('/proxy/studio/generate')) {
      if (generateResponse) return generateResponse
      return { ok: true, status: 200, json: async () => ({ job_id: 'job_1', filename: 'cat.png' }) }
    }
<<<<<<< HEAD
=======
    if (String(url).includes('/proxy/studio/sessions')) {
      return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', turns: [], jobs: [] }) }
    }
    if (String(url).includes('/proxy/studio/agent')) {
      return { ok: true, status: 200, json: async () => agentDecision() }
    }
>>>>>>> origin/main
    if (String(url).includes('/proxy/studio/characters')) {
      return { ok: true, status: 200, json: async () => ({ characters: [] }) }
    }
    if (String(url).includes('/proxy/studio/recipes')) {
      return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
    }
    return { ok: true, status: 200, json: async () => ({ available_guidance_tags: [] }) }
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

<<<<<<< HEAD
=======
/** Plan inspection is optional detail now, so it lives behind "advanced". */
function openAdvanced() {
  fireEvent.click(screen.getByRole('button', { name: /advanced/i }))
}

>>>>>>> origin/main
describe('ImageStudio fail-closed and renderer distinction (PR#355 findings 2-4)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  describe('renderers offline but gateway reachable (finding 3)', () => {
    beforeEach(() => {
      vi.mocked(queries.useImageStatus).mockReturnValue(offlineStatus() as never)
    })

    it('keeps the editor visible with generation disabled and a clear recovery', async () => {
      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByTestId('studio-offline')).toBeInTheDocument())

      // Renderer-independent surface stays usable.
      expect(screen.getByText(/no image engine is online/i)).toBeInTheDocument()
      expect(screen.getByTestId('studio-check-again')).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/describe what you want to create/i)).toBeInTheDocument()

      // Generation is present but disabled — not removed, never dispatched.
<<<<<<< HEAD
      const generate = screen.getByRole('button', { name: 'generate', exact: true })
      expect(generate).toBeDisabled()
=======
      const send = screen.getByTestId('studio-send')
      expect(send).toBeDisabled()
>>>>>>> origin/main

      // Plan preview remains available offline (finding 3). With a prompt entered,
      // the button is clickable even while engines are down.
      fireEvent.change(screen.getByPlaceholderText(/describe what you want to create/i), {
        target: { value: 'a sleeping cat' },
      })
<<<<<<< HEAD
=======
      openAdvanced()
>>>>>>> origin/main
      const plan = screen.getByRole('button', { name: 'preview plan', exact: true })
      expect(plan).not.toBeDisabled()

      // check again re-checks status rather than dispatching generation.
      const refetch = vi.mocked(queries.useImageStatus).mock.results[0]?.value?.refetch
      fireEvent.click(screen.getByTestId('studio-check-again'))
      expect(refetch).toHaveBeenCalled()
    })

    it('plan preview stays enabled and dispatches the planning route while offline', async () => {
      const fetchMock = stubStudioFetch()
      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByTestId('studio-offline')).toBeInTheDocument())

      const input = screen.getByPlaceholderText(/describe what you want to create/i)
      fireEvent.change(input, { target: { value: 'a sleeping cat' } })
<<<<<<< HEAD
=======
      openAdvanced()
>>>>>>> origin/main
      fireEvent.click(screen.getByRole('button', { name: 'preview plan', exact: true }))

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/proxy/studio/plan'),
          expect.objectContaining({ method: 'POST' }),
        )
      })
    })
  })

  describe('gateway unreachable (finding 2)', () => {
    it('shows the gateway failure state, not "start ComfyUI"', async () => {
      vi.mocked(queries.useImageStatus).mockReturnValue(errorStatus() as never)
      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByTestId('studio-status-error')).toBeInTheDocument())

      expect(screen.getByText(/can’t reach the image service/i)).toBeInTheDocument()
      expect(screen.getByText(/check that kitty’s gateway is running/i)).toBeInTheDocument()
      // Must NOT tell the user to start renderers when the failure is the gateway.
      expect(screen.queryByText(/start ComfyUI or Draw Things/i)).not.toBeInTheDocument()
      expect(screen.getByTestId('studio-check-again')).toBeInTheDocument()
    })
  })

  describe('raw HTML error document (finding 4)', () => {
    it('renders a human message with the <!DOCTYPE html> page as technical detail', async () => {
      vi.mocked(queries.useImageStatus).mockReturnValue(onlineStatus() as never)
      stubStudioFetch({
        ok: false,
        status: 500,
        text: async () => '<!DOCTYPE html><html><body><h1>Internal Server Error</h1></body></html>',
      })

      renderWithQueryClient(<ImageStudio />)
      await waitFor(() => expect(screen.getByPlaceholderText(/describe what you want to create/i)).toBeInTheDocument())

      fireEvent.change(screen.getByPlaceholderText(/describe what you want to create/i), {
        target: { value: 'a cat' },
      })
<<<<<<< HEAD
      fireEvent.click(screen.getByRole('button', { name: 'generate', exact: true }))
=======
      fireEvent.click(screen.getByTestId('studio-send'))
>>>>>>> origin/main

      // Primary message is human, not the raw HTML page.
      await waitFor(() => {
        expect(screen.getByText(/internal error — check your renderer/i)).toBeInTheDocument()
      })
      expect(screen.getByText('technical detail')).toBeInTheDocument()
      expect(screen.getByText(/<!doctype html>/i)).toBeInTheDocument()
    })
  })
})

describe('Enter-key handler tracks current renderer availability (PR#355 finding 5)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('Enter after an online→offline status transition does not dispatch /proxy/studio/generate', async () => {
    const fetchMock = stubStudioFetch()
    const statusMock = vi.mocked(queries.useImageStatus)
    statusMock.mockReturnValue(onlineStatus() as never)

    const { rerender, client } = renderWithQueryClient(<ImageStudio />)
    const input = screen.getByPlaceholderText(/describe what you want to create/i)
    fireEvent.change(input, { target: { value: 'a dramatic cat' } })

    // While online, Enter dispatches generation.
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/proxy/studio/generate'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    // The 30s status poll flips from online to offline after the prompt was last
    // edited — the exact stale-closure window that finding 5 reported.
    statusMock.mockReturnValue(offlineStatus() as never)
    rerender(
      <QueryClientProvider client={client}>
        <ImageStudio />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('studio-offline')).toBeInTheDocument())

    const generateCallsBeforeEnter = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('/proxy/studio/generate'),
    ).length

    // Enter must fail closed against the CURRENT status: no new generate dispatch
<<<<<<< HEAD
    // and the human offline message shows instead.
    fireEvent.keyDown(screen.getByPlaceholderText(/describe what you want to create/i), { key: 'Enter' })
=======
    // and the human offline message shows instead. The composer empties itself
    // after a send, so the follow-up request has to be typed again.
    const composer = screen.getByPlaceholderText(/describe what you want to create/i)
    fireEvent.change(composer, { target: { value: 'another dramatic cat' } })
    fireEvent.keyDown(composer, { key: 'Enter' })
>>>>>>> origin/main
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/no image engine is online/)
    })

    const generateCallsAfterEnter = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('/proxy/studio/generate'),
    ).length
    expect(generateCallsAfterEnter).toBe(generateCallsBeforeEnter)
  })
})

<<<<<<< HEAD
=======
describe('conversational Image Studio (issue #336, slice A5)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  /** Scripted studio backend: each agent turn returns the next queued decision. */
  function stubConversation(decisions: Record<string, unknown>[]) {
    let anchor: string | null = null
    const remaining = [...decisions]
    let jobCounter = 0
    const mock = vi.fn(async (url: string, init?: { method?: string; body?: string }) => {
      const target = String(url)
      if (target.includes('/proxy/studio/generate')) {
        jobCounter += 1
        return {
          ok: true,
          status: 200,
          json: async () => ({
            job_id: `job_${jobCounter}`,
            filename: `render_${jobCounter}.png`,
            recipe: 'comfyui_sdxl_standard',
          }),
        }
      }
      if (target.includes('/anchor')) {
        anchor = JSON.parse(init?.body ?? '{}').job_id
        return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', anchor_job_id: anchor }) }
      }
      if (target.includes('/proxy/studio/sessions')) {
        return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', turns: [], jobs: [] }) }
      }
      if (target.includes('/proxy/studio/agent')) {
        const next = remaining.shift() ?? agentDecision()
        return { ok: true, status: 200, json: async () => next }
      }
      if (target.includes('/proxy/studio/characters')) {
        return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      }
      if (target.includes('/proxy/studio/recipes')) {
        return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      }
      return { ok: true, status: 200, json: async () => ({ available_guidance_tags: [] }) }
    })
    vi.stubGlobal('fetch', mock)
    return mock
  }

  async function send(text: string) {
    const input = screen.getByPlaceholderText(/describe what you want to create/i)
    fireEvent.change(input, { target: { value: text } })
    fireEvent.click(screen.getByTestId('studio-send'))
  }

  beforeEach(() => {
    vi.mocked(queries.useImageStatus).mockReturnValue(onlineStatus() as never)
  })

  it('runs a two-turn conversation: generate, select a result, then edit it', async () => {
    const fetchMock = stubConversation([
      agentDecision({ summary: 'Rendering a golden-hour portrait.' }),
      agentDecision({
        action: 'edit',
        summary: 'Keeping the face and clothing, broadening the build.',
        plan_id: 'imgplan_2',
        operation: 'img2img',
        anchor_job_id: 'job_1',
        protected_traits: ['face', 'clothing'],
        requested_changes: ['broader build'],
      }),
    ])

    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-send')).toBeInTheDocument())

    // Turn one: a plain request produces one result inside the conversation.
    await send('a portrait in golden-hour light')
    await waitFor(() => {
      expect(screen.getByText('a portrait in golden-hour light')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('Rendering a golden-hour portrait.')).toBeInTheDocument()
    })
    await waitFor(() => expect(screen.getAllByTestId('studio-use-this')).toHaveLength(1))

    // The render dispatches from the approved plan, never from the raw prompt.
    const generateCall = fetchMock.mock.calls.find(([u]) =>
      String(u).includes('/proxy/studio/generate'),
    )
    expect(JSON.parse((generateCall?.[1] as { body: string }).body)).toMatchObject({
      plan_id: 'imgplan_1',
      session_id: 'imgses_1',
    })

    // "use this" selects that result as the anchor for what follows.
    fireEvent.click(screen.getAllByTestId('studio-use-this')[0])
    await waitFor(() => {
      expect(screen.getByTestId('studio-anchor-chip')).toBeInTheDocument()
    })

    // Turn two: the follow-up states what stays fixed and what changes.
    await send('keep his face and clothing, make the build broader')
    await waitFor(() => {
      expect(screen.getByTestId('studio-turn-protected')).toHaveTextContent(
        /staying fixed: face, clothing/i,
      )
    })
    expect(screen.getByTestId('studio-turn-changes')).toHaveTextContent(
      /changing: broader build/i,
    )
    await waitFor(() => expect(screen.getAllByTestId('studio-use-this')).toHaveLength(2))
  })

  it('a clarifying question is answered in the conversation and renders nothing', async () => {
    const fetchMock = stubConversation([
      agentDecision({
        action: 'clarify',
        summary: 'Which reference should I use?',
        plan_id: null,
        question: 'Which reference should I use?',
      }),
    ])

    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-send')).toBeInTheDocument())

    await send('make it better')
    await waitFor(() => {
      expect(screen.getByText('Which reference should I use?')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('studio-use-this')).not.toBeInTheDocument()
    expect(
      fetchMock.mock.calls.filter(([u]) => String(u).includes('/proxy/studio/generate')),
    ).toHaveLength(0)
  })

  it('a refusal is shown as an answer, not as an error banner', async () => {
    stubConversation([
      agentDecision({
        action: 'cancel',
        summary: 'There is no selected result to edit from.',
        plan_id: null,
        reason: 'There is no selected result to edit from.',
      }),
    ])

    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-send')).toBeInTheDocument())

    await send('make his build broader')
    await waitFor(() => {
      expect(screen.getByText('There is no selected result to edit from.')).toBeInTheDocument()
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('a failing controller names the image specialist, not the renderer', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const target = String(url)
      if (target.includes('/proxy/studio/sessions')) {
        return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1' }) }
      }
      if (target.includes('/proxy/studio/agent')) {
        return {
          ok: false,
          status: 500,
          text: async () => '<!DOCTYPE html><html><body><h1>Internal Server Error</h1></body></html>',
        }
      }
      if (target.includes('/proxy/studio/characters')) {
        return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      }
      if (target.includes('/proxy/studio/recipes')) {
        return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      }
      return { ok: true, status: 200, json: async () => ({ available_guidance_tags: [] }) }
    }))

    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-send')).toBeInTheDocument())

    await send('a portrait')
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /image specialist hit an internal error/i,
      )
    })
    expect(screen.queryByText(/check your renderer/i)).not.toBeInTheDocument()
  })

  it('the composer stays visible and empties itself after sending', async () => {
    stubConversation([agentDecision()])
    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-send')).toBeInTheDocument())

    await send('a portrait in golden-hour light')

    const input = screen.getByPlaceholderText(/describe what you want to create/i)
    await waitFor(() => expect(input).toHaveValue(''))
    expect(input).toBeInTheDocument()
  })
})

>>>>>>> origin/main
describe('operation-specific HTML error recovery (PR#355 finding 6)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('plan preview HTML 500 names the planning service, not the renderer', async () => {
    vi.mocked(queries.useImageStatus).mockReturnValue(offlineStatus() as never)
    vi.stubGlobal('fetch', vi.fn(async (url: string, _init?: unknown) => {
      if (String(url).includes('/proxy/studio/characters')) {
        return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      }
      if (String(url).includes('/proxy/studio/recipes')) {
        return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      }
      if (String(url).includes('/proxy/studio/plan')) {
        return { ok: false, status: 500, text: async () => '<!DOCTYPE html><html><body><h1>Internal Server Error</h1></body></html>' }
      }
      return { ok: true, status: 200, json: async () => ({ available_guidance_tags: [] }) }
    }))

    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByTestId('studio-offline')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText(/describe what you want to create/i), {
      target: { value: 'a sleeping cat' },
    })
<<<<<<< HEAD
=======
    openAdvanced()
>>>>>>> origin/main
    fireEvent.click(screen.getByRole('button', { name: 'preview plan', exact: true }))

    // The human message names the planning service; it must NOT blame the renderer.
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/planning service hit an internal error/i)
    })
    expect(screen.queryByText(/check your renderer/i)).not.toBeInTheDocument()
    // Raw HTML is preserved only in the expandable technical detail.
    expect(screen.getByText('technical detail')).toBeInTheDocument()
    expect(screen.getByText(/<!doctype html>/i)).toBeInTheDocument()
  })

  it('character creation HTML 500 names the character service, not the renderer', async () => {
    vi.mocked(queries.useImageStatus).mockReturnValue(onlineStatus() as never)
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: { method?: string }) => {
      const method = init?.method ?? 'GET'
      if (String(url).includes('/proxy/studio/characters') && method === 'GET') {
        return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      }
      if (String(url).includes('/proxy/studio/characters') && method === 'POST') {
        return { ok: false, status: 500, text: async () => '<!DOCTYPE html><html><body><h1>Internal Server Error</h1></body></html>' }
      }
      if (String(url).includes('/proxy/studio/recipes')) {
        return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      }
      return { ok: true, status: 200, json: async () => ({ available_guidance_tags: [] }) }
    }))

    renderWithQueryClient(<ImageStudio />)
    await waitFor(() => expect(screen.getByPlaceholderText(/describe what you want to create/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /character/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'new character' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'new character' }))
    fireEvent.change(await screen.findByPlaceholderText('character name'), { target: { value: 'Momo' } })
    fireEvent.click(screen.getByRole('button', { name: 'create', exact: true }))

    // The human message names the character service; it must NOT blame the renderer.
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/character service hit an internal error/i)
    })
    expect(screen.queryByText(/check your renderer/i)).not.toBeInTheDocument()
    // Raw HTML is preserved only in the expandable technical detail.
    expect(screen.getByText('technical detail')).toBeInTheDocument()
    expect(screen.getByText(/<!doctype html>/i)).toBeInTheDocument()
  })
})
