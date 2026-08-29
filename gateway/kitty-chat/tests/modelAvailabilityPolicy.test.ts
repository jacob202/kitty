import { describe, expect, it } from 'vitest'
import { MODELS } from '../src/lib/types'
import {
  isDirectProviderReady,
  resolveChatModels,
  reconcileOneShotOverride,
} from '../src/lib/model-availability'

const quick = MODELS.find(model => model.id === 'kitty-small')!
const code = MODELS.find(model => model.id === 'kitty-code')!

describe('chat model availability policy', () => {
  it('fails closed when curated and runtime model truth do not intersect', () => {
    const result = resolveChatModels({
      gatewayModels: [code],
      runtimeModelIds: ['kitty-small'],
      runtimeReady: true,
      curatedReady: true,
      directProviderReady: false,
    })
    expect(result).toEqual({ models: [], live: false })
  })

  it('keeps one honest chat route available for an explicitly selected configured direct provider', () => {
    const result = resolveChatModels({
      gatewayModels: [],
      runtimeModelIds: undefined,
      runtimeReady: false,
      curatedReady: false,
      directProviderReady: true,
    })
    expect(result.live).toBe(true)
    expect(result.models.map(model => model.id)).toEqual(['kitty-default'])
  })

  it('recognizes only an active configured and enabled direct provider', () => {
    const base = {
      order: ['openrouter'], warnings: [], config_path: 'test',
      providers: [{
        name: 'openrouter', base_url: 'https://example.test', model: 'x', model_env: null,
        api_key_env: ['OPENROUTER_API_KEY'], requires_key: true, configured: true,
        disabled: false, position: 0, kind: 'api_credit', free_tier: false,
      }],
    }
    expect(isDirectProviderReady({ ...base, active: 'openrouter' })).toBe(true)
    expect(isDirectProviderReady({ ...base, active: 'auto' })).toBe(false)
    expect(isDirectProviderReady({ ...base, active: 'openrouter', providers: [{ ...base.providers[0], disabled: true }] })).toBe(false)
  })

  it('clears a one-shot override withdrawn from the verified shortlist', () => {
    expect(reconcileOneShotOverride(code, [quick])).toBeNull()
    expect(reconcileOneShotOverride(quick, [quick])).toEqual(quick)
    expect(reconcileOneShotOverride(null, [quick])).toBeNull()
  })
})
