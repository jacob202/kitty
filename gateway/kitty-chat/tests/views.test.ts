import { describe, expect, it } from 'vitest'
import { REDIRECTS } from '../src/lib/views'

describe('view redirects', () => {
  it('redirects ordinary Builder navigation to Work', () => {
    expect(REDIRECTS.builder).toBe('work')
  })
})
