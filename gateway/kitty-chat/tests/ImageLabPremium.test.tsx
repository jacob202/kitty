import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ImageLab } from '../src/components/ImageLab'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return { ...actual, useImageStatus: vi.fn() }
})

const estimate = {
  provider: 'openrouter', model_id: 'vendor/image', recipe_id: 'hosted', routing_reason: 'best available', count: 2,
  per_image_estimate: { cost: { state: 'known', usd: 0.067 }, duration: { state: 'known', seconds: 12 } },
  estimate: { cost: { state: 'known', usd: 0.134 }, duration: { state: 'known', seconds: 24 } },
}
const batch = {
  batch_id: 'imgbatch_done', session_id: 'imgses_1', status: 'completed', count: 2, estimate: estimate.estimate,
  request: { prompt: 'two portrait options' },
  items: [
    { item_id: 'item_1', ordinal: 0, status: 'succeeded', job_id: 'job_1', error: null, result: { job_id: 'job_1', filename: 'one.png', routing_reason: 'route one' } },
    { item_id: 'item_2', ordinal: 1, status: 'succeeded', job_id: 'job_2', error: null, result: { job_id: 'job_2', filename: 'two.png', routing_reason: 'route two' } },
  ],
}

function stubFetch() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const target = String(url)
    if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
    if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
    if (target === '/proxy/studio/sessions/imgses_1') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', anchor_job_id: null, turns: [], jobs: [] }) }
    if (target.startsWith('/proxy/studio/batches?')) return { ok: true, status: 200, json: async () => ({ batches: [batch] }) }
    return { ok: true, status: 200, json: async () => ({}) }
  }))
}

describe('Image Lab premium workspace', () => {
  beforeEach(() => {
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_1')
    vi.mocked(queries.useImageStatus).mockReturnValue({
      data: { available: true, engines: [{ name: 'openrouter', label: 'OpenRouter', available: true }] },
      isPending: false, isError: false, refetch: vi.fn(),
    } as never)
    stubFetch()
  })
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); window.localStorage.clear() })

  it('puts route, recipe, estimate, and identity mode in visible preflight', async () => {
    render(<ImageLab />)
    const preflight = await screen.findByTestId('image-lab-preflight')
    await waitFor(() => expect(preflight).toHaveTextContent('openrouter'))
    expect(preflight).toHaveTextContent('vendor/image')
    expect(preflight).toHaveTextContent('hosted')
    expect(preflight).toHaveTextContent('$0.07')
    expect(preflight).toHaveTextContent('~12 sec')
    expect(preflight).toHaveTextContent('Balanced')
    expect(preflight).toHaveTextContent('best available')
  })

  it('lets the user lock GPT-Image-2 and carries that recipe through estimate and planning', async () => {
    window.localStorage.clear()
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      const method = init?.method ?? 'GET'
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [
        { recipe_id: 'openai_gpt_image_2', display_name: 'GPT-Image-2 (OpenAI)', provider: 'openai', quality_tier: 'quality', supports_img2img: true, is_available: true },
        { recipe_id: 'bfl_flux2_pro', display_name: 'FLUX.2 Pro', provider: 'flux2', quality_tier: 'quality', supports_img2img: true, is_available: true },
      ] }) }
      if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      if (target === '/proxy/studio/estimate') {
        const body = JSON.parse(String(init?.body ?? '{}'))
        return { ok: true, status: 200, json: async () => ({
          ...estimate, provider: body.recipe_id === 'openai_gpt_image_2' ? 'openai' : 'openrouter',
          model_id: body.recipe_id === 'openai_gpt_image_2' ? 'gpt-image-2' : 'vendor/image',
          recipe_id: body.recipe_id ?? 'hosted', operation: body.operation ?? 'txt2img',
        }) }
      }
      if (target === '/proxy/studio/sessions' && method === 'POST') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_openai', turns: [], jobs: [] }) }
      if (target === '/proxy/studio/agent') return { ok: true, status: 200, json: async () => ({
        action: 'generate', session_id: 'imgses_openai', summary: 'Rendering with GPT-Image-2.',
        plan_id: 'plan_openai', recipe_id: 'openai_gpt_image_2', protected_traits: [], requested_changes: [],
      }) }
      if (target === '/proxy/studio/batches' && method === 'POST') return { ok: true, status: 200, json: async () => ({
        batch_id: 'batch_openai', session_id: 'imgses_openai', status: 'queued', count: 1, estimate: estimate.estimate,
        request: { prompt: 'make a portrait' }, items: [{ item_id: 'i', ordinal: 0, status: 'queued', job_id: null, result: null, error: null }],
      }) }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    const route = await screen.findByRole('combobox', { name: 'generation route' })
    fireEvent.change(route, { target: { value: 'openai_gpt_image_2' } })

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/estimate'
      && JSON.parse(String((init as RequestInit | undefined)?.body ?? '{}')).recipe_id === 'openai_gpt_image_2'
    )).toBe(true))
    expect(await screen.findByTestId('image-lab-preflight')).toHaveTextContent('gpt-image-2')

    fireEvent.change(screen.getByRole('textbox', { name: 'Image request' }), { target: { value: 'make a portrait' } })
    fireEvent.click(screen.getByTestId('image-lab-send'))

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/agent'
      && JSON.parse(String((init as RequestInit | undefined)?.body ?? '{}')).recipe_id === 'openai_gpt_image_2'
    )).toBe(true))
    expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/batches'
      && JSON.parse(String((init as RequestInit | undefined)?.body ?? '{}')).recipe_id === 'openai_gpt_image_2'
    )).toBe(true)
  })

  it('lets two finished candidates open in a focused comparison dialog', async () => {
    render(<ImageLab />)
    await screen.findByRole('img', { name: 'Generated image 1' })
    fireEvent.click(screen.getByRole('button', { name: 'Select generated image 1 for comparison' }))
    fireEvent.click(screen.getByRole('button', { name: 'Select generated image 2 for comparison' }))
    fireEvent.click(screen.getByRole('button', { name: 'Compare 2 selected' }))

    const dialog = screen.getByRole('dialog', { name: 'Compare generated images' })
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveTextContent('job_1')
    expect(dialog).toHaveTextContent('job_2')
    expect(screen.getByRole('img', { name: 'Comparison image 1' })).toHaveAttribute('src', '/proxy/image/view/one.png')
    expect(screen.getByRole('img', { name: 'Comparison image 2' })).toHaveAttribute('src', '/proxy/image/view/two.png')
  })
})
