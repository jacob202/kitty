import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SettingsPanel } from '../src/components/SettingsPanel'
import { ToastProvider } from '../src/components/Toast'

vi.mock('../src/lib/queries', () => ({
  useGatewayModels: vi.fn(() => ({
    data: {
      models: [{ id: 'kitty-default', name: 'default', color: '#fff', glow: '#fff' }],
      fromLiveGateway: true,
      error: null,
    },
    isPending: false,
    isError: false,
  })),
  usePersonality: vi.fn(() => ({
    data: { soul: 'direct, warm, and specific\nsecond line', preferences: '- keep it brief' },
    isPending: false,
    isError: false,
  })),
  useUpdatePersonality: vi.fn(() => ({ isPending: false, isError: false, mutate: vi.fn() })),
  useUsageSummary: vi.fn(() => ({
    data: {
      totals: { calls: 4, tokens: 1200 }, estimated_cost: { usd: 0.01, cad: 0.02 },
      cost_estimate_disclaimer: 'Estimate only.',
    },
    isPending: false,
    isError: false,
  })),
}))

function renderWithToast(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>)
}

describe('SettingsPanel', () => {
  it('shows editable personality documents and truthful model/voice state', () => {
    renderWithToast(<SettingsPanel theme="cosmic" onToggleTheme={vi.fn()} />)

    expect(screen.getByLabelText('tone description')).toHaveValue('direct, warm, and specific\nsecond line')
    expect(screen.getByLabelText('standing preferences')).toHaveValue('- keep it brief')
    expect(screen.getByRole('button', { name: 'save personality' })).toBeInTheDocument()
    expect(screen.getByText('voice preview')).toBeInTheDocument()
    expect(screen.getByText('models and routing')).toBeInTheDocument()
    expect(screen.getByText('default')).toBeInTheDocument()
    expect(screen.getByText('usage')).toBeInTheDocument()
  })
})
