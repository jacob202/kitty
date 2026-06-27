import fs from 'node:fs'
import path from 'node:path'

import type { NextRequest } from 'next/server'

type ProxyEnv = {
  KITTY_GATEWAY_URL?: string
  KITTY_GATEWAY_SECRET?: string
  GATEWAY_SECRET?: string
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

export function resolveProxyConfig(
  env: ProxyEnv = process.env as ProxyEnv,
  repoEnv: ProxyEnv = readRepoEnv()
): { gatewayUrl: string; gatewaySecret: string } {
  return {
    gatewayUrl: resolveGatewayUrl(repoEnv.KITTY_GATEWAY_URL ?? env.KITTY_GATEWAY_URL),
    gatewaySecret: resolveGatewaySecret(
      repoEnv.KITTY_GATEWAY_SECRET ?? env.KITTY_GATEWAY_SECRET,
      repoEnv.GATEWAY_SECRET ?? env.GATEWAY_SECRET
    ),
  }
}

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { gatewayUrl, gatewaySecret } = resolveProxyConfig()
  const { path } = await params
  const target = `${gatewayUrl}/${path.join('/')}${req.nextUrl.search}`

  if (!gatewaySecret) {
    return Response.json(
      {
        error:
          'Proxy missing gateway secret. Set KITTY_GATEWAY_SECRET or GATEWAY_SECRET in the repo .env or process environment.',
      },
      { status: 503 }
    )
  }

  const headers: Record<string, string> = {}
  headers.Authorization = `Bearer ${gatewaySecret}`
  const ct = req.headers.get('content-type')
  if (ct) headers['Content-Type'] = ct

  const body = req.method !== 'GET' && req.method !== 'HEAD' ? req.body : null

  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      ...(body ? { body, duplex: 'half' } : {}),
    } as RequestInit)
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    throw new Error(`Proxy request failed for ${req.method} ${target}: ${detail}`)
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      'Content-Type': upstream.headers.get('content-type') ?? 'application/json',
      ...(upstream.headers.get('content-type')?.includes('text/event-stream')
        ? { 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' }
        : {}),
    },
  })
}

export const GET    = handler
export const POST   = handler
export const DELETE = handler
export const PUT    = handler
export const PATCH  = handler
