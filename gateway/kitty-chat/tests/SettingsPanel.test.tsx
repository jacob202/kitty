import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SettingsPanel } from '../src/components/SettingsPanel'

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

describe('SettingsPanel', () => {
  it('puts ordinary preferences before runtime details while preserving real state', () => {
    render(<SettingsPanel theme="cosmic" onToggleTheme={vi.fn()} />)

    expect(screen.getByLabelText('tone description')).toHaveValue('direct, warm, and specific\nsecond line')
    expect(screen.getByLabelText('standing preferences')).toHaveValue('- keep it brief')
    expect(screen.getByRole('button', { name: 'save personality' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Appearance' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Personality' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Models & usage' })).toBeInTheDocument()
    const headings = screen.getAllByRole('heading').map(node => node.textContent)
    expect(headings.indexOf('Personality')).toBeLessThan(headings.indexOf('Models & usage'))
    expect(screen.getByRole('button', { name: /switch theme/i })).toHaveStyle({ minHeight: '44px' })
    expect(screen.getAllByText('default').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('4 calls')).toBeInTheDocument()
    const technical = screen.getByText('Technical details').closest('details')
    expect(technical).not.toBeNull()
    expect(within(technical as HTMLElement).getByText(/127\.0\.0\.1:8000 via \/proxy/i)).toBeInTheDocument()
    expect(within(technical as HTMLElement).getByText('kitty-default')).toBeInTheDocument()
  })
})
