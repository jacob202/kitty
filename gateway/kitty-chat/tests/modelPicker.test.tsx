import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ModelSelectorCmdk } from '../src/components/ModelSelectorCmdk'
import { buildPickerModels, type GatewayModelPickerPayload } from '../src/lib/gateway'

const payload: GatewayModelPickerPayload = {
  schema_version: 1,
  source: 'test',
  discovery: { state: 'available', reason: null, checked_at: '2026-08-17T00:00:00Z' },
  claims: { role_tags: 'heuristic', alternatives: 'cost-screened only' },
  presets: [
    {
      role: 'auto', label: 'Daily Kitty', route: 'kitty-default', purpose: 'Choose the right lane.',
      kind: 'router', provider: null, model: null, configured: true,
      catalogue: null, catalogue_state: 'not_applicable', alternatives: [],
    },
    {
      role: 'code', label: 'Code', route: 'kitty-code', purpose: 'Repository implementation and debugging.',
      kind: 'model_role', provider: 'openrouter', model: 'vendor/coder', configured: true,
      catalogue_state: 'matched', alternatives: [],
      catalogue: {
        provider: 'openrouter', model: 'vendor/coder', name: 'Coder X', context_length: 200000,
        input_modalities: ['text'], output_modalities: ['text'], supported_parameters: ['tools'],
        pricing: { state: 'known', input_usd_per_million: 0.5, output_usd_per_million: 2, source: 'snapshot' },
        role_signal: { role: 'code', matches: true, basis: 'heuristic' },
        quality: { state: 'unknown', reason: 'not evaluated' },
        latency: { state: 'unknown', reason: 'not measured' },
      },
    },
  ],
}

describe('curated model picker', () => {
  afterEach(cleanup)

  it('maps role routes to selectable models while retaining exact upstream decision info', () => {
    const models = buildPickerModels(payload)
    expect(models.map(m => m.id)).toEqual(['kitty-default', 'kitty-code'])
    expect(models[0]).toMatchObject({ name: 'Daily Kitty', purpose: 'Choose the right lane.' })
    expect(models[1]).toMatchObject({
      name: 'Code', provider: 'openrouter', upstreamModel: 'vendor/coder', contextLength: 200000,
      inputUsdPerMillion: 0.5, outputUsdPerMillion: 2,
    })
  })

  it('shows a compact informed row instead of only a model name', () => {
    const models = buildPickerModels(payload)
    const onSelect = vi.fn()
    render(<ModelSelectorCmdk activeModel={models[0]} models={models} onSelectModel={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /Model: Daily Kitty/ }))

    expect(screen.getByText('Repository implementation and debugging.')).toBeInTheDocument()
    expect(screen.getByText('vendor/coder')).toBeInTheDocument()
    expect(screen.getByText(/200k context/i)).toBeInTheDocument()
    expect(screen.getByText(/\$0.50 in · \$2.00 out/i)).toBeInTheDocument()
  })
})
