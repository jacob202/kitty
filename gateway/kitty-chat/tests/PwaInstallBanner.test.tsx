import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PwaInstallBanner } from '../src/components/PwaInstallBanner'

describe('PwaInstallBanner', () => {
  afterEach(cleanup)

  it('renders an install button when the browser can install the app', () => {
    const onInstall = vi.fn()

    render(<PwaInstallBanner state="available" onInstall={onInstall} />)

    fireEvent.click(screen.getByRole('button', { name: 'install' }))
    expect(onInstall).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/dock launch/i)).toBeInTheDocument()
  })

  it('renders manual iOS instructions when beforeinstallprompt is unavailable', () => {
    render(<PwaInstallBanner state="manual-ios" />)

    const banner = screen.getByRole('status')

    expect(screen.getByText(/Add to Home Screen/i)).toBeInTheDocument()
    expect(banner.querySelector('button')).toBeNull()
  })

  it('renders a visible error when install setup fails', () => {
    render(<PwaInstallBanner state="error" error="Service worker registration failed: boom" />)

    expect(screen.getByRole('alert')).toHaveTextContent('Service worker registration failed: boom')
  })

  it('renders nothing when install chrome should stay hidden', () => {
    const { container } = render(<PwaInstallBanner state="hidden" />)
    expect(container.firstChild).toBeNull()
  })
})
