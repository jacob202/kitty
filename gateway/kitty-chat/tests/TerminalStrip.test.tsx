import { render, screen, cleanup, act, waitFor } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { TerminalStrip } from '../src/components/TerminalStrip'

describe('TerminalStrip', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders title and line count', () => {
    render(<TerminalStrip title="Gateway Log" maxLines={50} />)
    expect(screen.getByText('Gateway Log')).toBeInTheDocument()
    expect(screen.getByText('0 lines')).toBeInTheDocument()
  })

  it('shows logs with timestamps and levels', async () => {
    render(<TerminalStrip title="Log" maxLines={10} />)

    await act(async () => {
      vi.advanceTimersByTime(3000)
    })

    await waitFor(() => {
      expect(screen.getByText(/\d{2}:\d{2}:\d{2}/)).toBeInTheDocument()
    })
  })

  it('displays different log levels with colors', async () => {
    render(<TerminalStrip title="Log" maxLines={10} />)

    await act(async () => {
      vi.advanceTimersByTime(3000)
    })

    await waitFor(() => {
      expect(screen.getByText(/INFO|WARN|ERROR|DEBUG/)).toBeInTheDocument()
    })
  })

  it('respects maxLines prop', async () => {
    render(<TerminalStrip title="Log" maxLines={2} />)

    await act(async () => {
      vi.advanceTimersByTime(15000)
    })

    await waitFor(() => {
      const lines = screen.getAllByText(/\d{2}:\d{2}:\d{2}/)
      expect(lines.length).toBeLessThanOrEqual(2)
    })
  })

  it('renders default title when not provided', () => {
    render(<TerminalStrip />)
    expect(screen.getByText('terminal')).toBeInTheDocument()
  })
})
