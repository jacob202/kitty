import { describe, expect, it } from 'vitest'

import {
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
