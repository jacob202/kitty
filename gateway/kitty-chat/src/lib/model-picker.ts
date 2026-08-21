import type { Model } from './types'

const PICKER_URL = '/proxy/models/picker'

export interface GatewayModelPricing {
  state: 'known' | 'unknown'
  input_usd_per_million: number | null
  output_usd_per_million: number | null
  source: string | null
}

export interface GatewayModelCatalogueEntry {
  provider: string
  model: string
  name: string
  context_length: number | null
  input_modalities: string[]
  output_modalities: string[]
  supported_parameters: string[]
  pricing: GatewayModelPricing
  role_signal: { role: string; matches: boolean; basis: string }
  quality: { state: string; reason: string }
  latency: { state: string; reason: string }
}

export interface GatewayModelPickerPreset {
  role: string
  label: string
  route: string
  purpose: string
  kind: string
  provider: string | null
  model: string | null
  configured: boolean
  catalogue: GatewayModelCatalogueEntry | null
  catalogue_state: string
  alternatives: GatewayModelCatalogueEntry[]
}

export interface GatewayModelPickerPayload {
  schema_version: number
  source: string
  discovery: { state: string; reason: string | null; checked_at: string | null }
  presets: GatewayModelPickerPreset[]
  claims: { role_tags: string; alternatives: string }
}

const ROLE_COLORS: Record<string, { color: string; glow: string }> = {
  auto: { color: '#a884ff', glow: '#a884ff99' },
  fast: { color: '#9be86b', glow: '#9be86b99' },
  think: { color: '#21bdd9', glow: '#21bdd999' },
  code: { color: '#4d9fff', glow: '#4d9fff99' },
  vision: { color: '#f4c542', glow: '#f4c54299' },
}

export function buildPickerModels(payload: GatewayModelPickerPayload): Model[] {
  return payload.presets
    .filter(preset => preset.configured && typeof preset.route === 'string' && preset.route.length > 0)
    .map((preset, index) => {
      const palette = ROLE_COLORS[preset.role] ?? {
        color: ['#a884ff', '#21bdd9', '#9be86b', '#4d9fff', '#f4c542'][index % 5],
        glow: ['#a884ff99', '#21bdd999', '#9be86b99', '#4d9fff99', '#f4c54299'][index % 5],
      }
      const catalogue = preset.catalogue
      return {
        id: preset.route,
        name: preset.label,
        color: palette.color,
        glow: palette.glow,
        purpose: preset.purpose,
        provider: preset.provider,
        upstreamModel: preset.model,
        contextLength: catalogue?.context_length ?? null,
        inputUsdPerMillion: catalogue?.pricing.input_usd_per_million ?? null,
        outputUsdPerMillion: catalogue?.pricing.output_usd_per_million ?? null,
        capabilities: catalogue
          ? [...new Set([...catalogue.input_modalities, ...catalogue.supported_parameters])]
          : [],
        catalogueState: preset.catalogue_state,
      }
    })
}

export async function fetchModelPicker(signal?: AbortSignal): Promise<GatewayModelPickerPayload> {
  const response = await fetch(PICKER_URL, { signal })
  if (!response.ok) throw new Error(`model picker returned ${response.status}`)
  const payload = await response.json() as GatewayModelPickerPayload
  if (!payload || payload.schema_version !== 1 || !Array.isArray(payload.presets)) {
    throw new Error('model picker returned an invalid payload')
  }
  return payload
}
