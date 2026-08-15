import type { NextRequest } from 'next/server'

import {
  isTrustedProxyRequest,
  resolveProxyConfig,
} from '@/lib/gateway-proxy-config'

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const requestHost = req.headers.get('host') ?? req.nextUrl.host
  const requestOrigin = req.headers.get('origin') ?? undefined
  const edgeProof = req.headers.get('x-kitty-edge-verified') ?? undefined
  const { gatewayUrl, gatewaySecret, publicOrigin, edgeSharedSecret } = resolveProxyConfig()

  if (
    !isTrustedProxyRequest(
      requestHost,
      requestOrigin,
      edgeProof,
      publicOrigin,
      edgeSharedSecret
    )
  ) {
    return Response.json(
      { error: 'Kitty gateway proxy rejected an untrusted request.' },
      { status: 403 }
    )
  }
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

  const kittyHeaders = [
    'x-kitty-provider-selected',
    'x-kitty-model-requested',
    'x-kitty-model-selected',
    'x-kitty-tools-state',
    'x-kitty-runtime-revision',
    'x-kitty-turn-id',
    'x-kitty-attempt-id',
  ]
  const responseHeaders: Record<string, string> = {
    'Content-Type': upstream.headers.get('content-type') ?? 'application/json',
  }
  if (upstream.headers.get('content-type')?.includes('text/event-stream')) {
    responseHeaders['Cache-Control'] = 'no-cache'
    responseHeaders['X-Accel-Buffering'] = 'no'
  }
  for (const h of kittyHeaders) {
    const v = upstream.headers.get(h)
    if (v) responseHeaders[h] = v
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}

export const GET = handler
export const POST = handler
export const DELETE = handler
export const PUT = handler
export const PATCH = handler
