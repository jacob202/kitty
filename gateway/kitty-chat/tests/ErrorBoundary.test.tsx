import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ErrorBoundary } from '../src/components/ErrorBoundary'

function CrashingPanel({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Gateway returned 500 Internal Server Error')
  return <div>Recovered content</div>
}

function BoundaryHarness() {
  const [shouldThrow, setShouldThrow] = useState(true)

  return (
    <>
      <button type="button" onClick={() => setShouldThrow(false)}>make panel healthy</button>
      <ErrorBoundary name="library">
        <CrashingPanel shouldThrow={shouldThrow} />
      </ErrorBoundary>
    </>
  )
}

function CustomBoundaryHarness() {
  const [shouldThrow, setShouldThrow] = useState(true)

  return (
    <>
      <button type="button" onClick={() => setShouldThrow(false)}>make custom panel healthy</button>
      <ErrorBoundary
        fallback={(message, reset) => (
          <div role="alert">
            <div>{message}</div>
            <button type="button" onClick={reset}>custom retry</button>
          </div>
        )}
      >
        <CrashingPanel shouldThrow={shouldThrow} />
      </ErrorBoundary>
    </>
  )
}

afterEach(() => {
  cleanup()
})

describe('ErrorBoundary', () => {
  it('shows actionable copy without exposing the raw render error', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary name="library">
        <CrashingPanel shouldThrow />
      </ErrorBoundary>,
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Something went wrong in library')
    expect(alert).toHaveTextContent("Kitty's service hit an error. Try again in a moment.")
    expect(alert).not.toHaveTextContent('Gateway returned')
    expect(alert).not.toHaveTextContent('500')
    expect(screen.getByRole('button', { name: 'retry' })).toBeEnabled()

    consoleError.mockRestore()
  })

  it('retries the failed subtree after the user makes it healthy', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(<BoundaryHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'make panel healthy' }))
    fireEvent.click(screen.getByRole('button', { name: 'retry' }))

    expect(screen.getByText('Recovered content')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    consoleError.mockRestore()
  })

  it('gives custom fallbacks safe copy and keeps their retry action usable', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(<CustomBoundaryHarness />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent("Kitty's service hit an error. Try again in a moment.")
    expect(alert).not.toHaveTextContent('Gateway returned')
    expect(alert).not.toHaveTextContent('500')
    expect(screen.getByRole('button', { name: 'custom retry' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'make custom panel healthy' }))
    fireEvent.click(screen.getByRole('button', { name: 'custom retry' }))

    expect(screen.getByText('Recovered content')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    consoleError.mockRestore()
  })
})
