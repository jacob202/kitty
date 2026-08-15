import { afterEach, describe, expect, it, vi } from 'vitest'

import { NextRequest } from 'next/server'
import { GET as proxyGet } from '../src/app/proxy/[...path]/route'

import {
  isLoopbackHost,
  isTrustedProxyRequest,
  parseEnvText,
  resolveGatewaySecret,
  resolveGatewayUrl,
  resolveProxyConfig,
} from '../src/lib/gateway-proxy-config'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

describe('public proxy route', () => {
  it('forwards a verified public request while keeping the gateway secret server-side', async () => {
    vi.stubEnv('KITTY_PUBLIC_ORIGIN', 'https://kitty.example.com')
    vi.stubEnv('KITTY_EDGE_SHARED_SECRET', 'edge-secret')
    vi.stubEnv('KITTY_GATEWAY_SECRET', 'gateway-secret')

    const upstream = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      Response.json({ ok: true }, { status: 200 })
    )
    const request = new NextRequest('https://kitty.example.com/proxy/work', {
      headers: {
        host: 'kitty.example.com',
        origin: 'https://kitty.example.com',
        'x-kitty-edge-verified': 'edge-secret',
      },
    })

    const response = await proxyGet(request, { params: Promise.resolve({ path: ['work'] }) })

    expect(response.status).toBe(200)
    expect(upstream).toHaveBeenCalledTimes(1)
    const [url, init] = upstream.mock.calls[0]
    expect(url).toBe('http://127.0.0.1:8000/work')
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer gateway-secret')
  })

  it('rejects public traffic without edge verification before contacting Gateway', async () => {
    vi.stubEnv('KITTY_PUBLIC_ORIGIN', 'https://kitty.example.com')
    vi.stubEnv('KITTY_EDGE_SHARED_SECRET', 'edge-secret')
    vi.stubEnv('KITTY_GATEWAY_SECRET', 'gateway-secret')
    const upstream = vi.spyOn(globalThis, 'fetch')
    const request = new NextRequest('https://kitty.example.com/proxy/work', {
      headers: { host: 'kitty.example.com', origin: 'https://kitty.example.com' },
    })

    const response = await proxyGet(request, { params: Promise.resolve({ path: ['work'] }) })

    expect(response.status).toBe(403)
    expect(upstream).not.toHaveBeenCalled()
  })
})

describe('resolveGatewayUrl', () => {
  it('defaults to the canonical local gateway port', () => {
    expect(resolveGatewayUrl(undefined)).toBe('http://127.0.0.1:8000')
  })

  it('keeps an explicitly configured gateway URL', () => {
    expect(resolveGatewayUrl('http://127.0.0.1:8123')).toBe('http://127.0.0.1:8123')
  })
})

describe('resolveGatewaySecret', () => {
  it('prefers the explicit proxy secret', () => {
    expect(resolveGatewaySecret('proxy-secret', 'gateway-secret')).toBe('proxy-secret')
  })

  it('falls back to the gateway secret', () => {
    expect(resolveGatewaySecret(undefined, 'gateway-secret')).toBe('gateway-secret')
  })

  it('returns an empty string when both secrets are missing', () => {
    expect(resolveGatewaySecret(undefined, undefined)).toBe('')
  })
})

describe('proxy trust boundary', () => {
  it.each(['localhost:4000', '127.0.0.1:4000', '[::1]:4000'])(
    'accepts loopback host %s',
    (host) => {
      expect(isLoopbackHost(host)).toBe(true)
    }
  )

  it.each(['192.168.1.20:4000', '10.0.0.5:4000', 'kitty.tailnet:4000', undefined])(
    'rejects non-loopback host %s',
    (host) => {
      expect(isLoopbackHost(host)).toBe(false)
    }
  )

  it('accepts a same-origin loopback mutation', () => {
    expect(isTrustedProxyRequest('127.0.0.1:4000', 'http://127.0.0.1:4000')).toBe(true)
  })

  it('accepts a loopback request without Origin, such as navigation or curl', () => {
    expect(isTrustedProxyRequest('localhost:4000', undefined)).toBe(true)
  })

  it('rejects a cross-origin request even when both hosts are loopback', () => {
    expect(isTrustedProxyRequest('127.0.0.1:4000', 'http://127.0.0.1:3000')).toBe(false)
  })

  it('rejects a LAN request before the gateway secret can be forwarded', () => {
    expect(isTrustedProxyRequest('192.168.1.20:4000', 'http://192.168.1.20:4000')).toBe(
      false
    )
  })

  it('rejects malformed origins', () => {
    expect(isTrustedProxyRequest('localhost:4000', 'not a URL')).toBe(false)
  })

  it('accepts an exact HTTPS public origin only with the edge verification secret', () => {
    expect(
      isTrustedProxyRequest(
        'kitty.example.com',
        'https://kitty.example.com',
        'edge-secret',
        'https://kitty.example.com',
        'edge-secret'
      )
    ).toBe(true)
  })

  it('rejects a public request when the trusted edge proof is missing or wrong', () => {
    expect(
      isTrustedProxyRequest(
        'kitty.example.com',
        'https://kitty.example.com',
        undefined,
        'https://kitty.example.com',
        'edge-secret'
      )
    ).toBe(false)
    expect(
      isTrustedProxyRequest(
        'kitty.example.com',
        'https://kitty.example.com',
        'wrong',
        'https://kitty.example.com',
        'edge-secret'
      )
    ).toBe(false)
  })

  it('rejects wrong-host, wrong-origin, and non-HTTPS public configuration', () => {
    expect(
      isTrustedProxyRequest(
        'evil.example.com',
        'https://evil.example.com',
        'edge-secret',
        'https://kitty.example.com',
        'edge-secret'
      )
    ).toBe(false)
    expect(
      isTrustedProxyRequest(
        'kitty.example.com',
        'https://evil.example.com',
        'edge-secret',
        'https://kitty.example.com',
        'edge-secret'
      )
    ).toBe(false)
    expect(
      isTrustedProxyRequest(
        'kitty.example.com',
        'http://kitty.example.com',
        'edge-secret',
        'http://kitty.example.com',
        'edge-secret'
      )
    ).toBe(false)
  })
})

describe('parseEnvText', () => {
  it('parses plain and quoted dotenv values', () => {
    expect(
      parseEnvText(`
# comment
KITTY_GATEWAY_SECRET="proxy-secret"
GATEWAY_SECRET='gateway-secret'
KITTY_GATEWAY_URL=http://127.0.0.1:8123
`)
    ).toEqual({
      KITTY_GATEWAY_SECRET: 'proxy-secret',
      GATEWAY_SECRET: 'gateway-secret',
      KITTY_GATEWAY_URL: 'http://127.0.0.1:8123',
    })
  })
})

describe('resolveProxyConfig', () => {
  it('prefers explicit process env over repo .env', () => {
    expect(
      resolveProxyConfig(
        {
          KITTY_GATEWAY_URL: 'http://127.0.0.1:9999',
          KITTY_GATEWAY_SECRET: 'ambient-secret',
          GATEWAY_SECRET: 'ambient-gateway-secret',
        },
        {
          KITTY_GATEWAY_URL: 'http://127.0.0.1:8123',
          KITTY_GATEWAY_SECRET: 'repo-secret',
          GATEWAY_SECRET: 'repo-gateway-secret',
        }
      )
    ).toEqual({
      gatewayUrl: 'http://127.0.0.1:9999',
      gatewaySecret: 'ambient-secret',
      publicOrigin: '',
      edgeSharedSecret: '',
    })
  })

  it('falls back to the repo gateway secret when the proxy secret is unset', () => {
    expect(resolveProxyConfig({}, { GATEWAY_SECRET: 'repo-gateway-secret' })).toEqual({
      gatewayUrl: 'http://127.0.0.1:8000',
      gatewaySecret: 'repo-gateway-secret',
      publicOrigin: '',
      edgeSharedSecret: '',
    })
  })

  it('lets explicit process configuration override repo .env values', () => {
    expect(
      resolveProxyConfig(
        {
          KITTY_GATEWAY_URL: 'http://127.0.0.1:9000',
          KITTY_GATEWAY_SECRET: 'process-secret',
        },
        {
          KITTY_GATEWAY_URL: 'http://127.0.0.1:8123',
          KITTY_GATEWAY_SECRET: 'repo-secret',
        }
      )
    ).toMatchObject({
      gatewayUrl: 'http://127.0.0.1:9000',
      gatewaySecret: 'process-secret',
    })
  })

  it('does not consume repo .env configuration in production', () => {
    expect(
      resolveProxyConfig(
        { KITTY_ENV: 'production' },
        {
          KITTY_GATEWAY_URL: 'http://127.0.0.1:8123',
          KITTY_GATEWAY_SECRET: 'repo-secret',
          KITTY_PUBLIC_ORIGIN: 'https://repo.example.com',
          KITTY_EDGE_SHARED_SECRET: 'repo-edge-secret',
        }
      )
    ).toEqual({
      gatewayUrl: 'http://127.0.0.1:8000',
      gatewaySecret: '',
      publicOrigin: '',
      edgeSharedSecret: '',
    })
  })

  it('resolves public edge trust only from server-side configuration', () => {
    expect(
      resolveProxyConfig(
        {
          KITTY_PUBLIC_ORIGIN: 'https://kitty.example.com',
          KITTY_EDGE_SHARED_SECRET: 'edge-secret',
        },
        {}
      )
    ).toEqual({
      gatewayUrl: 'http://127.0.0.1:8000',
      gatewaySecret: '',
      publicOrigin: 'https://kitty.example.com',
      edgeSharedSecret: 'edge-secret',
    })
  })
})
