import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import EvalDashboard from '../EvalDashboard'

describe('EvalDashboard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders loading state initially', () => {
    // Mock fetch to never resolve so we see loading
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))
    render(<EvalDashboard />)
    expect(screen.getByText('Loading Eval Data...')).toBeInTheDocument()
  })

  it('renders error state on fetch failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))
    render(<EvalDashboard />)
    
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('renders eval dashboard with failed checks correctly', async () => {
    const mockData = {
      ok: true,
      dashboard: {
        artifact_count: 42,
        corrupt_count: 0,
        parsed_count: 42,
        latest: {
          run_id: 'test_run_123',
          suite: 'smoke',
          artifact: 'test_run_123_smoke.json',
          started_at: 1672531200, // Jan 1, 2023
          score: {
            passed: 8,
            total: 10,
            rate: 0.8
          },
          failed_checks: [
            'Test Check 1 failed',
            'Test Check 2 failed'
          ]
        },
        trend: {
          direction: 'down',
          delta: -0.1,
          previous_run_id: 'test_run_122'
        },
        recent: []
      }
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData)
    })

    render(<EvalDashboard />)

    // Wait for the data to load
    await waitFor(() => {
      expect(screen.getByText('EVAL DASHBOARD')).toBeInTheDocument()
    })

    // Check header
    expect(screen.getByText(/42 artifacts total/)).toBeInTheDocument()
    
    // Check pass rate
    expect(screen.getByText('80.0%')).toBeInTheDocument()

    // Check failed checks rendering
    expect(screen.getByText('Failed Checks')).toBeInTheDocument()
    expect(screen.getByText('Test Check 1 failed')).toBeInTheDocument()
    expect(screen.getByText('Test Check 2 failed')).toBeInTheDocument()
  })
})
