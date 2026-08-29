import fs from 'node:fs'
import path from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchGatewayModels } from '../src/lib/gateway'

function pickerPayload(route = 'kitty-code') {
  return {
    schema_version: 1,
    source: 'test',
    discovery: { state: 'available', reason: null, checked_at: null },
    claims: { role_tags: 'heuristic', alternatives: 'cost-screened only' },
    presets: [
      {
        role: 'code',
        label: 'Code',
        route,
        purpose: 'Repository work.',
        kind: 'model_role',
        provider: 'openrouter',
        model: 'qwen/qwen3-coder',
        configured: true,
        catalogue: null,
        catalogue_state: 'not_observed',
        alternatives: [],
      },
    ],
  }
}

describe('fail-closed model availability', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('keeps only the safe live/static intersection and reports degraded picker metadata', async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [{ id: 'kitty-code' }, { id: 'provider-internal' }] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ schema_version: 99, presets: [] }), { status: 200 }),
      )

    const result = await fetchGatewayModels()

    expect(result.fromLiveGateway).toBe(false)
    expect(result.error).toMatch(/model details unavailable/i)
    expect(result.models.map(model => model.id)).toEqual(['kitty-code'])
    expect(result.models.some(model => model.id === 'provider-internal')).toBe(false)
  })

  it('bounds a stalled picker request and reports the timeout', async () => {
    vi.useFakeTimers()
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [{ id: 'kitty-code' }] }), { status: 200 }),
      )
      .mockImplementationOnce((_url, init) => {
        const signal = init?.signal as AbortSignal | undefined
        return new Promise((_resolve, reject) => {
          const abort = () => {
            const error = new Error('The operation was aborted')
            error.name = 'AbortError'
            reject(error)
          }
          if (signal?.aborted) abort()
          else signal?.addEventListener('abort', abort, { once: true })
        })
      })

    const pending = fetchGatewayModels()
    await vi.advanceTimersByTimeAsync(8_000)
    const result = await pending

    expect(result.fromLiveGateway).toBe(false)
    expect(result.error).toMatch(/timed out/i)
    expect(result.models.map(model => model.id)).toEqual(['kitty-code'])
  })

  it('fails model availability closed when no curated live route exists', async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [{ id: 'provider-internal' }] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(pickerPayload()), { status: 200 }),
      )

    const result = await fetchGatewayModels()

    expect(result.fromLiveGateway).toBe(false)
    expect(result.models).toEqual([])
    expect(result.error).toMatch(/no live curated models/i)
  })

  it('guards every chat dispatch entry point while model availability is unavailable', () => {
    const page = fs.readFileSync(path.resolve(__dirname, '../src/app/page.tsx'), 'utf8')

    expect(page).toContain('const modelUnavailable = !k.modelGateway.live || k.availableModels.length === 0')
    expect(page).toContain("onSend={(text) => { if (!modelUnavailable) k.handleRuntimeSend(text) }}")
    expect(page).toContain("onReload={() => { if (!modelUnavailable) k.handleRetry() }}")
    expect(page).toContain("onRetry: () => { if (!modelUnavailable) k.handleRetry() },")
    expect(page).toContain("onSend={() => { if (!modelUnavailable) k.handleSend() }}")
    expect(page).toContain('disabled={k.isStreaming || modelUnavailable}')
  })
})
