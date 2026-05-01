import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SettingsModal from '../app/components/SettingsModal'
import { ToastProvider } from '../app/components/Toast'

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('SettingsModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    currentMode: 'hardware',
    onModeChange: vi.fn(),
    isLightMode: false,
    onLightModeToggle: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        features: {
          auto_pagination: { enabled: true, description: "desc" },
        },
        models: {
          primary: "claude",
        }
      })
    })
  })

  it('renders when open', async () => {
    render(
      <ToastProvider>
        <SettingsModal {...defaultProps} />
      </ToastProvider>
    )
    
    await waitFor(() => {
      expect(screen.getByText('KITTY CONTROL PANEL')).toBeInTheDocument()
    })
    expect(screen.getByText('Appearance')).toBeInTheDocument()
    expect(screen.getByText('Features')).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', () => {
    render(
      <ToastProvider>
        <SettingsModal {...defaultProps} />
      </ToastProvider>
    )
    
    fireEvent.click(screen.getByText('Close'))
    expect(defaultProps.onClose).toHaveBeenCalled()
  })

  it('calls onLightModeToggle when toggle clicked', () => {
    render(
      <ToastProvider>
        <SettingsModal {...defaultProps} />
      </ToastProvider>
    )
    
    // Find the toggle button in Appearance section
    const toggle = screen.getByText('Light Mode').closest('div')?.parentElement?.querySelector('button')
    if (toggle) {
      fireEvent.click(toggle)
      expect(defaultProps.onLightModeToggle).toHaveBeenCalled()
    }
  })
})
