import { describe, it, expect } from 'vitest'
import { MODELS, CHAT_COLORS, COLOR_CYCLE } from '../src/lib/types'

describe('types', () => {
  it('MODELS has 5 entries', () => {
    expect(MODELS).toHaveLength(5)
  })

  it('each model has id, name, color, glow', () => {
    for (const model of MODELS) {
      expect(model).toHaveProperty('id')
      expect(model).toHaveProperty('name')
      expect(model).toHaveProperty('color')
      expect(model).toHaveProperty('glow')
    }
  })

  it('CHAT_COLORS has all color keys', () => {
    expect(Object.keys(CHAT_COLORS)).toEqual(
      expect.arrayContaining(COLOR_CYCLE)
    )
  })

  it('COLOR_CYCLE has 5 entries', () => {
    expect(COLOR_CYCLE).toHaveLength(5)
  })
})
