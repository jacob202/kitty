import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { describe, expect, it, afterEach, vi } from 'vitest'

import { TerminalStrip } from '../src/components/TerminalStrip'

vi.mock('../src/lib/gateway', () => ({
  fetchLogTail: vi.fn(),
}))

import { fetchLogTail } from '../src/lib/gateway'

const mockedTail = vi.mocked(fetchLogTail)

describe('TerminalStrip', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders title and real log lines from the gateway', async () => {
    mockedTail.mockResolvedValue({
      file: 'gateway.log',
      lines: ['INFO: 127.0.0.1 - "GET /health HTTP/1.1" 200 OK', 'WARNING: slow request'],
    })
    render(<TerminalStrip title="gateway log" />)
    expect(screen.getByText('gateway log')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/GET \/health/)).toBeInTheDocument()
    })
    expect(screen.getByText('2 lines')).toBeInTheDocument()
    expect(mockedTail).toHaveBeenCalledWith('gateway', 100)
  })

  it('shows empty state when the log has no lines', async () => {
    mockedTail.mockResolvedValue({ file: 'gateway.log', lines: [] })
    render(<TerminalStrip />)
    await waitFor(() => {
      expect(screen.getByText('nothing logged yet')).toBeInTheDocument()
    })
  })

  it('shows a deadpan error when the gateway is unreachable', async () => {
    mockedTail.mockRejectedValue(new Error('down'))
    render(<TerminalStrip />)
    await waitFor(() => {
      expect(screen.getByText('log unavailable. is the gateway up?')).toBeInTheDocument()
    })
  })

  it('renders default title when not provided', async () => {
    mockedTail.mockResolvedValue({ file: 'gateway.log', lines: [] })
    render(<TerminalStrip />)
    expect(screen.getByText('gateway log')).toBeInTheDocument()
  })
})
