import { describe, expect, it } from 'vitest'

import { resolveGatewayUrl } from '../src/app/proxy/[...path]/route'

describe('resolveGatewayUrl', () => {
  it('defaults to the canonical local gateway port', () => {
    expect(resolveGatewayUrl(undefined)).toBe('http://127.0.0.1:8000')
  })

  it('keeps an explicitly configured gateway URL', () => {
    expect(resolveGatewayUrl('http://127.0.0.1:8123')).toBe('http://127.0.0.1:8123')
  })
})
