import { describe, expect, it } from 'vitest'

import {
  isLoopbackHost,
  isTrustedProxyRequest,
  parseEnvText,
  resolveGatewaySecret,
  resolveGatewayUrl,
  resolveProxyConfig,
} from '../src/lib/gateway-proxy-config'

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
  it('prefers repo env over ambient process env', () => {
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
      gatewayUrl: 'http://127.0.0.1:8123',
      gatewaySecret: 'repo-secret',
    })
  })

  it('falls back to the repo gateway secret when the proxy secret is unset', () => {
    expect(resolveProxyConfig({}, { GATEWAY_SECRET: 'repo-gateway-secret' })).toEqual({
      gatewayUrl: 'http://127.0.0.1:8000',
      gatewaySecret: 'repo-gateway-secret',
    })
  })
})
