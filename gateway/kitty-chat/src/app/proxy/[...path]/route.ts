import type { NextRequest } from 'next/server'

const OWUI = process.env.KITTY_GATEWAY_URL    ?? 'http://127.0.0.1:8000'
export function resolveGatewayUrl(configuredUrl: string | undefined): string {
  return configuredUrl ?? 'http://127.0.0.1:8000'
}

const OWUI = resolveGatewayUrl(process.env.KITTY_GATEWAY_URL)
const KEY  = process.env.KITTY_GATEWAY_SECRET ?? ''

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  const target = `${OWUI}/${path.join('/')}${req.nextUrl.search}`

  const headers: Record<string, string> = {}
  if (KEY) headers['Authorization'] = `Bearer ${KEY}`
  const ct = req.headers.get('content-type')
  if (ct) headers['Content-Type'] = ct

  const body = req.method !== 'GET' && req.method !== 'HEAD' ? req.body : null

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    ...(body ? { body, duplex: 'half' } : {}),
  } as RequestInit)

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
