import { describe, expect, it } from 'vitest'
import { REDIRECTS } from '../src/lib/views'

describe('view redirects', () => {
  it('keeps the full Builder cockpit reachable', () => {
    expect(REDIRECTS.builder).toBeUndefined()
  })
})
