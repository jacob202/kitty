import fs from 'node:fs'
import path from 'node:path'

type ProxyEnv = {
  KITTY_GATEWAY_URL?: string
  KITTY_GATEWAY_SECRET?: string
  GATEWAY_SECRET?: string
  KITTY_PUBLIC_ORIGIN?: string
  KITTY_EDGE_SHARED_SECRET?: string
  KITTY_ENV?: string
}

export function resolveGatewayUrl(configuredUrl: string | undefined): string {
  return configuredUrl?.trim() || 'http://127.0.0.1:8000'
}

export function resolveGatewaySecret(
  proxySecret: string | undefined,
  gatewaySecret: string | undefined
): string {
  return proxySecret?.trim() || gatewaySecret?.trim() || ''
}

function parseHost(host: string | undefined): URL | null {
  const value = host?.trim()
  if (!value) return null

  try {
    return new URL(`http://${value}`)
  } catch {
    return null
  }
}

export function isLoopbackHost(host: string | undefined): boolean {
  const parsed = parseHost(host)
  if (!parsed) return false

  const hostname = parsed.hostname.replace(/^\[|\]$/g, '').toLowerCase()
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
}

export function isTrustedProxyRequest(
  host: string | undefined,
  origin: string | undefined,
  edgeProof?: string,
  publicOrigin?: string,
  expectedEdgeSecret?: string
): boolean {
  const configuredPublicOrigin = publicOrigin?.trim() || ''
  const configuredEdgeSecret = expectedEdgeSecret?.trim() || ''

  if (configuredPublicOrigin || configuredEdgeSecret) {
    if (!configuredPublicOrigin || !configuredEdgeSecret || edgeProof !== configuredEdgeSecret) {
      return false
    }

    const parsedHost = parseHost(host)
    if (!parsedHost) return false

    try {
      const trustedOrigin = new URL(configuredPublicOrigin)
      if (trustedOrigin.protocol !== 'https:') return false
      if (parsedHost.host.toLowerCase() !== trustedOrigin.host.toLowerCase()) return false
      if (!origin) return true
      return new URL(origin).origin === trustedOrigin.origin
    } catch {
      return false
    }
  }

  const parsedHost = parseHost(host)
  if (!parsedHost || !isLoopbackHost(host)) return false
  if (!origin) return true

  try {
    const parsedOrigin = new URL(origin)
    return (
      parsedOrigin.protocol === 'http:' &&
      parsedOrigin.hostname.replace(/^\[|\]$/g, '').toLowerCase() ===
        parsedHost.hostname.replace(/^\[|\]$/g, '').toLowerCase() &&
      parsedOrigin.port === parsedHost.port
    )
  } catch {
    return false
  }
}

export function parseEnvText(text: string): Record<string, string> {
  const values: Record<string, string> = {}

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#') || !line.includes('=')) {
      continue
    }

    const [rawKey, ...rawValueParts] = line.split('=')
    const rawValue = rawValueParts.join('=')
    values[rawKey.trim()] = rawValue.trim().replace(/^['"]|['"]$/g, '')
  }

  return values
}

function findKittyRepoRoot(startDir: string): string | null {
  let current = path.resolve(startDir)

  while (true) {
    if (
      fs.existsSync(path.join(current, 'AGENTS.md')) &&
      fs.existsSync(path.join(current, 'gateway'))
    ) {
      return current
    }

    const parent = path.dirname(current)
    if (parent === current) {
      return null
    }
    current = parent
  }
}

function readRepoEnv(): Record<string, string> {
  const repoRoot = findKittyRepoRoot(process.cwd())
  if (!repoRoot) {
    return {}
  }

  const envPath = path.join(repoRoot, '.env')
  if (!fs.existsSync(envPath)) {
    return {}
  }

  return parseEnvText(fs.readFileSync(envPath, 'utf8'))
}

/**
 * Resolve the proxy configuration without exposing configuration values to
 * client code. This lives outside the route because Next route modules may
 * export only HTTP handlers and route configuration.
 */
export function resolveProxyConfig(
  env: ProxyEnv = process.env as ProxyEnv,
  repoEnv: ProxyEnv = readRepoEnv()
): {
  gatewayUrl: string
  gatewaySecret: string
  publicOrigin: string
  edgeSharedSecret: string
} {
  // Development may fall back to the repo-local .env for convenience. A
  // production process must be configured only by its deployment environment:
  // otherwise a stale developer .env can silently override the deployed
  // gateway, auth secret, or public trust boundary.
  const repoFallback = env.KITTY_ENV?.trim().toLowerCase() === 'production' ? {} : repoEnv
  return {
    gatewayUrl: resolveGatewayUrl(env.KITTY_GATEWAY_URL ?? repoFallback.KITTY_GATEWAY_URL),
    gatewaySecret: resolveGatewaySecret(
      env.KITTY_GATEWAY_SECRET ?? repoFallback.KITTY_GATEWAY_SECRET,
      env.GATEWAY_SECRET ?? repoFallback.GATEWAY_SECRET
    ),
    publicOrigin: env.KITTY_PUBLIC_ORIGIN?.trim() || repoFallback.KITTY_PUBLIC_ORIGIN?.trim() || '',
    edgeSharedSecret:
      env.KITTY_EDGE_SHARED_SECRET?.trim() || repoFallback.KITTY_EDGE_SHARED_SECRET?.trim() || '',
  }
}
