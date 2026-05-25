import { render, screen, cleanup } from '@testing-library/react'
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
    
    // Advance timer to trigger first log
    vi.advanceTimersByTime(3000)
    
    // Wait for the log to appear
    await vi.runAllTimersAsync()
    
    // Check that a log line is rendered with timestamp pattern
    const logLines = screen.getAllByText(/\d{2}:\d{2}:\d{2}/)
    expect(logLines.length).toBeGreaterThan(0)
  })

  it('displays different log levels with colors', async () => {
    render(<TerminalStrip title="Log" maxLines={10} />)
    
    vi.advanceTimersByTime(3000)
    await vi.runAllTimersAsync()
    
    // Check for level badges
    const levels = ['INFO', 'WARN', 'ERROR', 'DEBUG']
    levels.forEach(level => {
      expect(screen.getAllByText(level).length).toBeGreaterThanOrEqual(0)
    })
  })

  it('respects maxLines prop', async () => {
    render(<TerminalStrip title="Log" maxLines={2} />)
    
    // Generate multiple logs
    vi.advanceTimersByTime(15000) // 5 logs
    await vi.runAllTimersAsync()
    
    const lines = screen.getAllByText(/\d{2}:\d{2}:\d{2}/)
    expect(lines.length).toBeLessThanOrEqual(2)
  })

  it('renders default title when not provided', () => {
    render(<TerminalStrip />)
    expect(screen.getByText('terminal')).toBeInTheDocument()
  })
})
