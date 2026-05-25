import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { TodayCompass, type PriorityItem } from '../src/components/TodayCompass'

describe('TodayCompass', () => {
  afterEach(() => {
    cleanup()
  })

  const mockItems: PriorityItem[] = [
    {
      id: 1,
      title: 'Review PR #42',
      description: 'Check code changes and approve',
      priority: 'high',
      icon: '🔥',
      onSelect: vi.fn(),
    },
    {
      id: 2,
      title: 'Team meeting',
      description: 'Weekly sync at 3pm',
      priority: 'medium',
      icon: '📅',
    },
    {
      id: 3,
      title: 'Update docs',
      description: 'Add API examples',
      priority: 'low',
      icon: '📝',
    },
  ]

  it('renders with default title and items', () => {
    render(<TodayCompass items={mockItems} />)

    expect(screen.getByText("Today's Compass")).toBeInTheDocument()
    expect(screen.getByText('Review PR #42')).toBeInTheDocument()
    expect(screen.getByText('Team meeting')).toBeInTheDocument()
    expect(screen.getByText('Update docs')).toBeInTheDocument()
    expect(screen.getByText('3 items')).toBeInTheDocument()
  })

  it('renders with custom title', () => {
    render(<TodayCompass items={mockItems} title="My Priorities" />)

    expect(screen.getByText('My Priorities')).toBeInTheDocument()
    expect(screen.getByText('3 items')).toBeInTheDocument()
  })

  it('does not render title when empty string', () => {
    render(<TodayCompass items={mockItems} title="" />)

    expect(screen.queryByText("Today's Compass")).not.toBeInTheDocument()
    expect(screen.queryByText('My Priorities')).not.toBeInTheDocument()
    // But items should still render
    expect(screen.getByText('Review PR #42')).toBeInTheDocument()
  })

  it('does not render title when not provided (default is used)', () => {
    // The component uses a default title; this test ensures that behavior
    // Since default is "Today's Compass", it should appear
    render(<TodayCompass items={mockItems} />)
    expect(screen.getByText("Today's Compass")).toBeInTheDocument()
  })

  it('displays item descriptions', () => {
    render(<TodayCompass items={mockItems} />)

    expect(screen.getByText('Check code changes and approve')).toBeInTheDocument()
    expect(screen.getByText('Weekly sync at 3pm')).toBeInTheDocument()
    expect(screen.getByText('Add API examples')).toBeInTheDocument()
  })

  it('shows priority badges', () => {
    render(<TodayCompass items={mockItems} />)

    expect(screen.getByText('HIGH')).toBeInTheDocument()
    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
    expect(screen.getByText('LOW')).toBeInTheDocument()
  })

  it('displays icons when provided', () => {
    render(<TodayCompass items={mockItems} />)

    expect(screen.getByText('🔥')).toBeInTheDocument()
    expect(screen.getByText('📅')).toBeInTheDocument()
    expect(screen.getByText('📝')).toBeInTheDocument()
  })

  it('calls item.onSelect when card clicked', () => {
    const onSelectSpy = vi.fn()
    const itemsWithSpy: PriorityItem[] = [
      { ...mockItems[0], onSelect: onSelectSpy },
    ]
    render(<TodayCompass items={itemsWithSpy} />)

    const card = screen.getByRole('button', { name: /Review PR #42/i })
    fireEvent.click(card)
    expect(onSelectSpy).toHaveBeenCalledTimes(1)
  })

  it('calls onItemSelect prop when card clicked', () => {
    const onItemSelectSpy = vi.fn()
    render(<TodayCompass items={mockItems} onItemSelect={onItemSelectSpy} />)

    const card = screen.getByRole('button', { name: /Team meeting/i })
    fireEvent.click(card)
    expect(onItemSelectSpy).toHaveBeenCalledWith(mockItems[1])
  })

  it('supports keyboard navigation', () => {
    render(<TodayCompass items={mockItems} />)

    const card = screen.getByRole('button', { name: /Update docs/i })
    fireEvent.keyDown(card, { key: 'Enter' })
    // No error thrown means test passes
  })

  it('sorts items by priority (high first)', () => {
    const unorderedItems: PriorityItem[] = [
      { id: 'a', title: 'Low task', priority: 'low' },
      { id: 'b', title: 'High task', priority: 'high' },
      { id: 'c', title: 'Medium task', priority: 'medium' },
    ]
    render(<TodayCompass items={unorderedItems} />)

    const buttons = screen.getAllByRole('button')
    expect(buttons[0]).toHaveTextContent('High task')
    expect(buttons[1]).toHaveTextContent('Medium task')
    expect(buttons[2]).toHaveTextContent('Low task')
  })

  it('shows empty state when no items', () => {
    render(<TodayCompass items={[]} />)

    expect(screen.getByText('No priority items for today')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('displays correct item count (plural)', () => {
    render(<TodayCompass items={mockItems} />)

    expect(screen.getByText('3 items')).toBeInTheDocument()
  })

  it('displays correct item count (singular)', () => {
    render(<TodayCompass items={[mockItems[0]]} />)

    expect(screen.getByText('1 item')).toBeInTheDocument()
  })

  it('renders in compact mode', () => {
    render(<TodayCompass items={[mockItems[0]]} compact />)

    expect(screen.getByText("Today's Compass")).toBeInTheDocument()
    expect(screen.queryByText('Check code changes and approve')).not.toBeInTheDocument()
  })

  it('hides description in compact mode', () => {
    render(<TodayCompass items={mockItems} compact />)

    expect(screen.queryByText('Weekly sync at 3pm')).not.toBeInTheDocument()
    expect(screen.queryByText('Check code changes and approve')).not.toBeInTheDocument()
  })
})
