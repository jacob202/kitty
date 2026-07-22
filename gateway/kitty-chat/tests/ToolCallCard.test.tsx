import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ToolCallCard, detectToolCalls, stripToolBlocks } from '../src/components/shared/ToolCallCard'

afterEach(cleanup)

describe('ToolCallCard', () => {
  it('renders with name and running state', () => {
    render(<ToolCallCard name="search_web" state="running">Searching...</ToolCallCard>)
    expect(screen.getByText('search_web')).toBeDefined()
    expect(screen.getByText('running')).toBeDefined()
  })

  it('renders done state with duration', () => {
    render(<ToolCallCard name="generate_image" state="done" duration="2.3s">Result</ToolCallCard>)
    expect(screen.getByText('done')).toBeDefined()
    expect(screen.getByText('2.3s')).toBeDefined()
  })

  it('renders failed state with error', () => {
    render(<ToolCallCard name="fetch_url" state="failed" error="timeout after 30s">Attempted fetch</ToolCallCard>)
    expect(screen.getByText('failed')).toBeDefined()
    expect(screen.getByText('timeout after 30s')).toBeDefined()
  })

  it('toggles expanded on header click', () => {
    render(<ToolCallCard name="test" state="done">hidden content</ToolCallCard>)
    expect(screen.queryByText('hidden content')).toBeNull()
    fireEvent.click(screen.getByText('test'))
    expect(screen.getByText('hidden content')).toBeDefined()
  })

  it('auto-expands when running', () => {
    render(<ToolCallCard name="test" state="running">streaming...</ToolCallCard>)
    expect(screen.getByText('streaming...')).toBeDefined()
  })

  it('has correct aria-label', () => {
    render(<ToolCallCard name="do_thing" state="running">...</ToolCallCard>)
    expect(screen.getByRole('status', { name: 'tool do_thing: running' })).toBeDefined()
  })
})

describe('detectToolCalls', () => {
  it('detects wrench emoji tool calls', () => {
    const result = detectToolCalls('🔧 search_web\nquery: latest news\n───')
    expect(result).toHaveLength(1)
    expect(result[0].toolName).toBe('search_web')
    expect(result[0].blocks).toEqual(['query: latest news'])
  })

  it('detects bracket tool syntax', () => {
    const result = detectToolCalls('[tool:fetch_url]\nGET https://example.com\n')
    expect(result).toHaveLength(1)
    expect(result[0].toolName).toBe('fetch_url')
  })

  it('detects multiple tool calls', () => {
    const content = '🔧 search\nresult 1\n───\nSome text\n🔧 fetch\nresult 2\n'
    const result = detectToolCalls(content)
    expect(result).toHaveLength(2)
    expect(result[0].toolName).toBe('search')
    expect(result[1].toolName).toBe('fetch')
  })

  it('returns empty for plain text', () => {
    const result = detectToolCalls('Hello, how are you?')
    expect(result).toHaveLength(0)
  })

  it('returns empty for empty content', () => {
    expect(detectToolCalls('')).toHaveLength(0)
    expect(detectToolCalls(null as unknown as string)).toHaveLength(0)
  })
})

describe('stripToolBlocks', () => {
  it('removes tool blocks from content', () => {
    const content = 'Hello\n🔧 search\nquery: hi\n───\nGoodbye'
    const result = stripToolBlocks(content)
    expect(result).toBe('Hello\nGoodbye')
  })

  it('returns original content when no tools present', () => {
    const content = 'Just a regular message'
    expect(stripToolBlocks(content)).toBe('Just a regular message')
  })

  it('collapses excessive blank lines', () => {
    const content = 'Hello\n\n🔧 tool\n\nresult\n\n───\n\n\n\nGoodbye'
    const result = stripToolBlocks(content)
    expect(result).not.toContain('\n\n\n')
  })
})
