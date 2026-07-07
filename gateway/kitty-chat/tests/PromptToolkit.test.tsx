import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { PromptToolkit } from '../src/components/PromptToolkit'

describe('PromptToolkit', () => {
  afterEach(cleanup)

  const mockTemplates = [
    { id: 1, title: 'Brainstorm', content: 'Help me brainstorm ideas for...', category: 'Creative', icon: '💡' },
    { id: 2, title: 'Debug Code', content: 'Help me debug this code:\n\n```\n\n```', category: 'Technical', icon: '🔧' },
    { id: 3, title: 'Summarize', content: 'Summarize the following text:\n\n', category: 'Analysis', icon: '📄' },
  ]

  it('renders title and count', () => {
    render(<PromptToolkit templates={mockTemplates} />)
    expect(screen.getByText('Prompt Toolkit')).toBeInTheDocument()
    expect(screen.getByText('3 templates')).toBeInTheDocument()
  })

  it('groups templates by category', () => {
    render(<PromptToolkit templates={mockTemplates} />)
    expect(screen.getByText('Creative')).toBeInTheDocument()
    expect(screen.getByText('Technical')).toBeInTheDocument()
    expect(screen.getByText('Analysis')).toBeInTheDocument()
  })

  it('shows template title and preview', () => {
    render(<PromptToolkit templates={mockTemplates} />)
    expect(screen.getByText('Brainstorm')).toBeInTheDocument()
    expect(screen.getByText(/Help me brainstorm/)).toBeInTheDocument()
  })

  it('calls onSelect when template clicked', () => {
    const onSelect = vi.fn()
    render(<PromptToolkit templates={mockTemplates} onSelect={onSelect} />)

    fireEvent.click(screen.getByText('Brainstorm'))
    expect(onSelect).toHaveBeenCalledWith(mockTemplates[0])
  })

  it('supports keyboard navigation', () => {
    const onSelect = vi.fn()
    render(<PromptToolkit templates={mockTemplates} onSelect={onSelect} />)

    const brainstormCard = screen.getByText('Brainstorm').closest('div[role="button"]')!
    fireEvent.keyDown(brainstormCard, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalled()
  })

  it('shows empty state when no templates', () => {
    render(<PromptToolkit templates={[]} />)
    expect(screen.getByText('no prompt templates yet')).toBeInTheDocument()
  })

  it('renders custom title', () => {
    render(<PromptToolkit templates={mockTemplates} title="My Prompts" />)
    expect(screen.getByText('My Prompts')).toBeInTheDocument()
  })

  it('handles templates without category', () => {
    const uncategorized = [{ id: 1, title: 'Generic', content: 'Do something' }]
    render(<PromptToolkit templates={uncategorized} />)
    expect(screen.getByText('General')).toBeInTheDocument()
  })
})
