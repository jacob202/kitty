import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SettingsShell from '../src/components/SettingsShell'

vi.mock('../src/components/SettingsPanel', () => ({
  SettingsPanel: () => <section aria-label="personal preferences">preferences</section>,
}))
vi.mock('../src/components/ProviderCenter', () => ({
  ProviderCenter: () => <div>provider diagnostics body</div>,
}))

describe('SettingsShell hierarchy', () => {
  it('keeps personal preferences primary and provider diagnostics progressively disclosed', () => {
    render(<SettingsShell isMobile={false} theme="cosmic" onToggleTheme={vi.fn()} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument()
    const preferences = screen.getByLabelText('personal preferences')
    const providerDetails = screen.getByText('Provider & runtime details').closest('details')
    expect(providerDetails).not.toBeNull()
    expect(preferences.compareDocumentPosition(providerDetails as Node) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(providerDetails as HTMLElement).getByText('provider diagnostics body')).toBeInTheDocument()
    expect(screen.queryByText(/data export, cache management, and debug overlays/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/skills & tools/i)).not.toBeInTheDocument()
  })
})
