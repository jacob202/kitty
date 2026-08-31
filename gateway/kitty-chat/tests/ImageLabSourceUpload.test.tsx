import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ImageLab } from '../src/components/ImageLab'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return { ...actual, useImageStatus: vi.fn() }
  it('restores a legacy anchor preview from the job canonical artifact', async () => {
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_legacy')
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const target = String(url)
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      if (target === '/proxy/studio/sessions/imgses_legacy') return { ok: true, status: 200, json: async () => ({
        session_id: 'imgses_legacy', anchor_job_id: 'job_old', anchor_artifact_id: 'provider_asset_old', turns: [],
        jobs: [{ job_id: 'job_old', canonical_artifact_id: 'artifact_image_job_old' }],
      }) }
      if (target.startsWith('/proxy/studio/batches?')) return { ok: true, status: 200, json: async () => ({ batches: [] }) }
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
      return { ok: true, status: 200, json: async () => ({}) }
    }))

    render(<ImageLab />)

    expect(await screen.findByRole('img', { name: 'Selected edit source' })).toHaveAttribute(
      'src', '/proxy/artifacts/artifact_image_job_old/content',
    )
  })

})

const estimate = {
  provider: 'openai', model_id: 'gpt-image-2', recipe_id: 'openai_gpt_image_2', routing_reason: 'selected', count: 1,
  per_image_estimate: { cost: { state: 'unknown', usd: null }, duration: { state: 'unknown', seconds: null } },
  estimate: { cost: { state: 'unknown', usd: null }, duration: { state: 'unknown', seconds: null } },
}

function uploadResult() {
  return {
    job: { job_id: 'job_upload', provider: 'upload', operation: 'import', canonical_artifact_id: 'artifact_source' },
    artifact: { id: 'artifact_source' },
    session: { session_id: 'imgses_1', anchor_job_id: 'job_upload', anchor_artifact_id: 'artifact_source' },
    quality: { has_blockers: false, has_warnings: false, is_perfect: true, summary: 'reference looks good', advice: [], dimensions: '1024×768' },
  }
}

function makeFetch() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const target = String(url)
    if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
    if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
    if (target === '/proxy/studio/sessions/imgses_1') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_1', anchor_job_id: null, anchor_artifact_id: null, turns: [], jobs: [] }) }
    if (target.startsWith('/proxy/studio/batches?')) return { ok: true, status: 200, json: async () => ({ batches: [] }) }
    if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
    if (target === '/proxy/studio/sessions/imgses_1/source-image' && init?.method === 'POST') return { ok: true, status: 200, json: async () => uploadResult() }
    return { ok: true, status: 200, json: async () => ({}) }
  })
}

describe('Image Lab external edit source', () => {
  beforeEach(() => {
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_1')
    vi.mocked(queries.useImageStatus).mockReturnValue({
      data: { available: true, engines: [{ name: 'openai', label: 'GPT-Image-2', available: true }] },
      isPending: false, isError: false, refetch: vi.fn(),
    } as never)
  })
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); window.localStorage.clear() })

  it('uploads a source image, previews its artifact, and switches preflight to img2img', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    render(<ImageLab />)

    const file = new File(['image'], 'source.png', { type: 'image/png' })
    fireEvent.change(await screen.findByLabelText('Upload source image'), { target: { files: [file] } })

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/sessions/imgses_1/source-image' && (init as RequestInit | undefined)?.method === 'POST'
    )).toBe(true))
    expect(await screen.findByRole('img', { name: 'Selected edit source' })).toHaveAttribute(
      'src', '/proxy/artifacts/artifact_source/content',
    )
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/estimate'
      && JSON.parse(String((init as RequestInit | undefined)?.body ?? '{}')).operation === 'img2img'
    )).toBe(true))
  })

  it('accepts a dropped source image through the same durable import path', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    render(<ImageLab />)

    const file = new File(['image'], 'dropped.webp', { type: 'image/webp' })
    fireEvent.drop(await screen.findByTestId('image-source-dropzone'), { dataTransfer: { files: [file] } })

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/proxy/studio/sessions/imgses_1/source-image' && (init as RequestInit | undefined)?.body instanceof FormData
    )).toBe(true))
    expect(await screen.findByTestId('image-lab-anchor')).toHaveTextContent('Selected image is the edit source')
  })
  it('restores a legacy anchor preview from the job canonical artifact', async () => {
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_legacy')
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const target = String(url)
      if (target === '/proxy/studio/recipes') return { ok: true, status: 200, json: async () => ({ recipes: [] }) }
      if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      if (target === '/proxy/studio/sessions/imgses_legacy') return { ok: true, status: 200, json: async () => ({
        session_id: 'imgses_legacy', anchor_job_id: 'job_old', anchor_artifact_id: 'provider_asset_old', turns: [],
        jobs: [{ job_id: 'job_old', canonical_artifact_id: 'artifact_image_job_old' }],
      }) }
      if (target.startsWith('/proxy/studio/batches?')) return { ok: true, status: 200, json: async () => ({ batches: [] }) }
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => estimate }
      return { ok: true, status: 200, json: async () => ({}) }
    }))

    render(<ImageLab />)

    expect(await screen.findByRole('img', { name: 'Selected edit source' })).toHaveAttribute(
      'src', '/proxy/artifacts/artifact_image_job_old/content',
    )
  })

})
