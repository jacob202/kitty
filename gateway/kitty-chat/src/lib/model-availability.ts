import { MODELS, type Model } from './types'

export type ProviderAvailability = {
  active: string
  providers: Array<{ name: string; configured: boolean; disabled: boolean }>
}

export function isDirectProviderSelected(chain: ProviderAvailability | null | undefined): boolean {
  return Boolean(chain?.active && chain.active !== 'auto')
}

export function isDirectProviderReady(chain: ProviderAvailability | null | undefined): boolean {
  if (!isDirectProviderSelected(chain)) return false
  const selected = chain!.providers.find(provider => provider.name === chain!.active)
  return Boolean(selected?.configured && !selected.disabled)
}

export function resolveChatModels(input: {
  gatewayModels: Model[]
  runtimeModelIds: string[] | null | undefined
  runtimeReady: boolean
  curatedReady: boolean
  directProviderReady: boolean
  directProviderSelected: boolean
}): { models: Model[]; live: boolean } {
  if (input.directProviderSelected && !input.directProviderReady) {
    return { models: [], live: false }
  }
  if (input.directProviderReady) {
    const daily = MODELS.find(model => model.id === 'kitty-default')
    return { models: daily ? [daily] : [], live: Boolean(daily) }
  }
  if (!input.runtimeReady || !input.curatedReady) {
    return { models: input.gatewayModels, live: false }
  }
  if (!input.runtimeModelIds) return { models: [], live: false }
  const runtimeIds = new Set(input.runtimeModelIds)
  const models = input.gatewayModels.filter(model => runtimeIds.has(model.id))
  return { models, live: models.length > 0 }
}

export function reconcileOneShotOverride(override: Model | null, available: Model[]): Model | null {
  if (!override) return null
  return available.some(model => model.id === override.id) ? override : null
}
