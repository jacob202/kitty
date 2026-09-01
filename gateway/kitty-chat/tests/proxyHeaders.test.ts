import { describe, expect, it } from 'vitest'

import { copyProxyHeaders } from '../src/lib/gateway-proxy-headers'

describe('artifact proxy range headers', () => {
  it('copies byte-range request and response headers', () => {
    const request = {
      get: (name: string) => ({ range: 'bytes=10-20', 'if-range': 'etag-1' } as Record<string, string>)[name.toLowerCase()] ?? null,
    } as Headers
    expect(copyProxyHeaders(request, ['range', 'if-range'])).toEqual({
      range: 'bytes=10-20',
      'if-range': 'etag-1',
    })

    const response = new Headers({ 'Accept-Ranges': 'bytes', 'Content-Range': 'bytes 10-20/100', 'Content-Length': '11' })
    expect(copyProxyHeaders(response, ['accept-ranges', 'content-range', 'content-length'])).toEqual({
      'accept-ranges': 'bytes',
      'content-range': 'bytes 10-20/100',
      'content-length': '11',
    })
  })
})
