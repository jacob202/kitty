import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { InsightFeed } from '../src/components/InsightFeed'
import type { GatewayInsight } from '../src/lib/gateway'

describe('InsightFeed', () => {
  afterEach(cleanup)

  const mockInsights: GatewayInsight[] = [
    {
      insight_id: 'insight-1',
      kind: 'pattern',
      title: 'You often ask about weather in the morning',
      detail: 'Detected 5 morning weather queries this week',
      source: 'pattern detection',
      created_at: Date.now() / 1000,
    },
    {
      insight_id: 'insight-2',
      kind: 'suggestion',
      title: 'Set up a daily weather loop',
      actions: [{ label: 'Create Loop', action_id: 'create-loop' }],
      created_at: Date.now() / 1000 - 3600,
    },
    {
      insight_id: 'insight-3',
      kind: 'anomaly',
      title: 'Unusual activity detected',
      detail: 'High token usage spike',
      created_at: Date.now() / 1000 - 7200,
    },
  ]

  it('renders title and count', () => {
    render(<InsightFeed insights={mockInsights} />)
    expect(screen.getByText('Insights')).toBeInTheDocument()
    expect(screen.getByText('3 new')).toBeInTheDocument()
  })

  it('shows insights sorted by created_at descending', () => {
    render(<InsightFeed insights={mockInsights} />)
    const titles = screen.getAllByText(/weather in the morning|daily weather loop|Unusual activity detected/)
    expect(titles[0]).toHaveTextContent('weather in the morning')
  })

  it('displays insight kind badge', () => {
    render(<InsightFeed insights={mockInsights} />)
    expect(screen.getByText('PATTERN')).toBeInTheDocument()
    expect(screen.getByText('SUGGESTION')).toBeInTheDocument()
    expect(screen.getByText('ANOMALY')).toBeInTheDocument()
  })

  it('shows detail and source when provided', () => {
    render(<InsightFeed insights={mockInsights} />)
    expect(screen.getByText(/Detected 5 morning weather/)).toBeInTheDocument()
    expect(screen.getByText(/Source: pattern detection/)).toBeInTheDocument()
  })

  it('shows action buttons when actions exist', () => {
    render(<InsightFeed insights={mockInsights} />)
    expect(screen.getByRole('button', { name: 'Create Loop' })).toBeInTheDocument()
  })

  it('calls onAction when action button clicked', () => {
    const onAction = vi.fn()
    render(<InsightFeed insights={mockInsights} onAction={onAction} />)

    fireEvent.click(screen.getByRole('button', { name: 'Create Loop' }))
    expect(onAction).toHaveBeenCalledWith('insight-2', 'create-loop')
  })

  it('calls onDismiss when dismiss button clicked', () => {
    const onDismiss = vi.fn()
    render(<InsightFeed insights={mockInsights} onDismiss={onDismiss} />)

    const dismissButtons = screen.getAllByRole('button', { name: 'Dismiss' })
    fireEvent.click(dismissButtons[0])
    expect(onDismiss).toHaveBeenCalledWith('insight-1')
  })

  it('shows empty state when no insights', () => {
    render(<InsightFeed insights={[]} />)
    expect(screen.getByText('no new insights')).toBeInTheDocument()
  })

  it('renders custom title', () => {
    render(<InsightFeed insights={mockInsights} title="Recent Insights" />)
    expect(screen.getByText('Recent Insights')).toBeInTheDocument()
  })
})
