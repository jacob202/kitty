import type { NextRequest } from 'next/server'

import { resolveProxyConfig } from '@/lib/gateway-proxy-config'

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
