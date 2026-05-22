import { describe, expect, it } from 'vitest'
import {
  activeTodos,
  formatGatewayWeather,
  resolveWeatherText,
} from '../src/lib/dashboardHome'

describe('dashboardHome helpers', () => {
  it('filters active todos by pending and in_progress', () => {
    const todos = [
      { id: 1, content: 'a', status: 'pending' },
      { id: 2, content: 'b', status: 'completed' },
      { id: 3, content: 'c', status: 'in_progress' },
    ]
    expect(activeTodos(todos)).toHaveLength(2)
  })

  it('formats live weather from gateway payload', () => {
    expect(formatGatewayWeather({ description: 'Sunny', temp_c: -2 })).toBe('Sunny, -2°C')
  })

  it('prefers live weather over headline fallback', () => {
    const text = resolveWeatherText(
      { description: 'Cloudy', temp_c: 4 },
      { headlines: ['Weather: storm warning'] } as never,
    )
    expect(text).toBe('Cloudy, 4°C')
  })
})
