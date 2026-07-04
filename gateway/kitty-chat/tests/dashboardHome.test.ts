import { describe, expect, it } from 'vitest'
import { activeTodos } from '../src/lib/dashboardHome'

describe('dashboardHome helpers', () => {
  it('filters active todos by pending and in_progress', () => {
    const todos = [
      { id: 1, content: 'a', status: 'pending' },
      { id: 2, content: 'b', status: 'completed' },
      { id: 3, content: 'c', status: 'in_progress' },
    ]
    expect(activeTodos(todos)).toHaveLength(2)
  })
})
