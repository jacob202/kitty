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

  it('carries the Auto preflight recipe into the agent plan request', async () => {
    window.localStorage.clear()
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      const method = init?.method ?? 'GET'
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [
        { recipe_id: 'openrouter_auto', display_name: 'OpenRouter image', provider: 'openrouter', quality_tier: 'quality', supports_img2img: true, is_available: true },
      ] }) }
      if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => ({ ...estimate, recipe_id: 'openrouter_auto' }) }
      if (target === '/proxy/studio/sessions' && method === 'POST') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_auto', turns: [], jobs: [] }) }
      if (target === '/proxy/studio/agent') return { ok: true, status: 200, json: async () => ({ action: 'generate', session_id: 'imgses_auto', summary: 'Rendering.', plan_id: 'plan_auto', recipe_id: 'openrouter_auto', protected_traits: [], requested_changes: [] }) }
      if (target === '/proxy/studio/batches' && method === 'POST') return { ok: true, status: 200, json: async () => ({ batch_id: 'batch_auto', session_id: 'imgses_auto', status: 'queued', count: 1, estimate: estimate.estimate, request: { prompt: 'auto route portrait' }, items: [] }) }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    await screen.findByTestId('image-lab-preflight')
    fireEvent.change(screen.getByRole('textbox', { name: 'Image request' }), { target: { value: 'auto route portrait' } })
    fireEvent.click(screen.getByTestId('image-lab-send'))

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/agent'
      && JSON.parse(String((init as RequestInit | undefined)?.body ?? '{}')).recipe_id === 'openrouter_auto'
    )).toBe(true))
  })

  it('disables recipes whose live engine is offline even when registry metadata says available', async () => {
    vi.mocked(queries.useImageStatus).mockReturnValue({
      data: { available: true, engines: [
        { name: 'openrouter', label: 'OpenRouter', available: true },
        { name: 'comfyui', label: 'ComfyUI', available: false, unavailable_reason: 'ComfyUI is offline' },
      ] },
      isPending: false, isError: false, refetch: vi.fn(),
    } as never)
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const target = String(url)
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [
        { recipe_id: 'comfyui_pulid_sdxl', display_name: 'PuLID SDXL Identity', provider: 'comfyui', quality_tier: 'maximum', supports_img2img: true, is_available: true },
        { recipe_id: 'openrouter_auto', display_name: 'OpenRouter image', provider: 'openrouter', quality_tier: 'quality', supports_img2img: true, is_available: true },
      ] }) }
      if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      if (target === '/proxy/studio/sessions/imgses_1') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', anchor_job_id: null, turns: [], jobs: [] }) }
      if (target.startsWith('/proxy/studio/batches?')) return { ok: true, status: 200, json: async () => ({ batches: [] }) }
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
      return { ok: true, status: 200, json: async () => ({}) }
    }))

    render(<ImageLab />)
    const route = await screen.findByRole('combobox', { name: 'generation route' })
    const offline = Array.from(route.querySelectorAll('option')).find(option => option.value === 'comfyui_pulid_sdxl')
    const online = Array.from(route.querySelectorAll('option')).find(option => option.value === 'openrouter_auto')
    expect(offline).toBeDisabled()
    expect(offline).toHaveTextContent('unavailable')
    expect(online).not.toBeDisabled()
  })

  it('lets two finished candidates open in a focused comparison dialog', async () => {
    render(<ImageLab />)
    await screen.findByRole('img', { name: 'Generated image 1' })
    fireEvent.click(screen.getByRole('button', { name: 'Select generated image 1 for comparison' }))
    fireEvent.click(screen.getByRole('button', { name: 'Select generated image 2 for comparison' }))
    fireEvent.click(screen.getByRole('button', { name: 'Compare 2 selected' }))

    const dialog = screen.getByRole('dialog', { name: 'Compare generated images' })
    expect(dialog).toBeInTheDocument()
    expect(dialog).not.toHaveTextContent('candidate comparison')
    expect(screen.getByRole('button', { name: 'Close comparison' })).toHaveFocus()
    expect(dialog).toHaveTextContent('job_1')
    expect(dialog).toHaveTextContent('job_2')
    expect(screen.getByRole('img', { name: 'Comparison image 1' })).toHaveAttribute('src', '/proxy/image/view/one.png')
    expect(screen.getByRole('img', { name: 'Comparison image 2' })).toHaveAttribute('src', '/proxy/image/view/two.png')
  })

  it('shows and safely edits the durable character profile in place', async () => {
    window.localStorage.clear()
    const character = {
      character_id: 'char_profile', name: 'Mia', description: 'Portrait anchor for editorial scenes.',
      preferred_recipe: 'openai_gpt_image_2', identity_preset: 'identity_first',
      references: [{ ref_id: 'ref_1', is_primary: true, original_name: 'mia.jpg', storage_path: '/tmp/mia.jpg' }],
    }
    const updated = {
      ...character,
      name: 'Mia Reference',
      description: 'Keep facial identity stable across portrait edits.',
      identity_preset: 'balanced',
    }
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      const method = init?.method ?? 'GET'
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [{
        recipe_id: 'openai_gpt_image_2', display_name: 'GPT-Image-2 (OpenAI)', provider: 'openai',
        quality_tier: 'quality', operation: 'txt2img', supports_img2img: true,
        supports_characters: true, max_characters: 1, is_available: true,
      }] }) }
      if (target === '/proxy/studio/characters' && method === 'GET') {
        return { ok: true, status: 200, json: async () => ({ characters: [character] }) }
      }
      if (target === '/proxy/studio/characters/char_profile' && method === 'PATCH') {
        return { ok: true, status: 200, json: async () => updated }
      }
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    fireEvent.click(await screen.findByTestId('image-lab-character-picker'))
    fireEvent.click(await screen.findByText('Mia'))

    const profile = await screen.findByTestId('image-lab-character-profile')
    expect(profile).toHaveTextContent('Portrait anchor for editorial scenes.')
    expect(profile).toHaveTextContent('Identity first')
    expect(profile).toHaveTextContent('GPT-Image-2 (OpenAI)')
    expect(profile).toHaveTextContent('1 reference')
    expect(screen.getByRole('combobox', { name: 'identity' })).toHaveValue('identity_first')

    fireEvent.click(screen.getByRole('button', { name: /edit character profile/i }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Character profile name' }), { target: { value: 'Mia Reference' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Character profile description' }), { target: { value: 'Keep facial identity stable across portrait edits.' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Character identity protection' }), { target: { value: 'balanced' } })
    fireEvent.click(screen.getByRole('button', { name: /save character profile/i }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url) === '/proxy/studio/characters/char_profile'
      && (init as RequestInit | undefined)?.method === 'PATCH'
      && JSON.stringify(JSON.parse(String((init as RequestInit).body))) === JSON.stringify({
        name: 'Mia Reference',
        description: 'Keep facial identity stable across portrait edits.',
        identity_preset: 'balanced',
      })
    ))).toBe(true))
    expect(profile).toHaveTextContent('Mia Reference')
    expect(profile).toHaveTextContent('Keep facial identity stable across portrait edits.')
    expect(profile).toHaveTextContent('Balanced')
    expect(profile).toHaveTextContent('GPT-Image-2 (OpenAI)')
    expect(screen.getByRole('combobox', { name: 'identity' })).toHaveValue('balanced')
  })


  it('keeps character profile edits recoverable when the first save fails', async () => {
    window.localStorage.clear()
    const character = {
      character_id: 'char_retry', name: 'Retry Mia', description: 'Original profile.',
      preferred_recipe: null, identity_preset: 'balanced', references: [],
    }
    let patchAttempts = 0
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      const method = init?.method ?? 'GET'
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      if (target === '/proxy/studio/characters' && method === 'GET') {
        return { ok: true, status: 200, json: async () => ({ characters: [character] }) }
      }
      if (target === '/proxy/studio/characters/char_retry' && method === 'PATCH') {
        patchAttempts += 1
        if (patchAttempts === 1) return { ok: false, status: 503, text: async () => 'profile save temporarily unavailable' }
        const body = JSON.parse(String(init?.body ?? '{}'))
        return { ok: true, status: 200, json: async () => ({ ...character, ...body }) }
      }
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    fireEvent.click(await screen.findByTestId('image-lab-character-picker'))
    fireEvent.click(await screen.findByText('Retry Mia'))
    fireEvent.click(screen.getByRole('button', { name: /edit character profile/i }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Character profile name' }), { target: { value: 'Retry Mia Saved' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Character profile description' }), { target: { value: 'Recovered without losing the edit.' } })
    fireEvent.click(screen.getByRole('button', { name: /save character profile/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('profile save temporarily unavailable')
    expect(screen.getByRole('textbox', { name: 'Character profile name' })).toHaveValue('Retry Mia Saved')
    expect(screen.getByRole('textbox', { name: 'Character profile description' })).toHaveValue('Recovered without losing the edit.')

    fireEvent.click(screen.getByRole('button', { name: /save character profile/i }))
    await screen.findByRole('button', { name: /edit character profile/i })
    const profile = screen.getByTestId('image-lab-character-profile')
    expect(profile).toHaveTextContent('Retry Mia Saved')
    expect(profile).toHaveTextContent('Recovered without losing the edit.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(patchAttempts).toBe(2)
  })

})
