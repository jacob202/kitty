export const PROXY_REQUEST_PASSTHROUGH_HEADERS = ['range', 'if-range'] as const
export const PROXY_RESPONSE_PASSTHROUGH_HEADERS = [
  'accept-ranges',
  'content-range',
  'content-length',
  'etag',
  'last-modified',
] as const

export function copyProxyHeaders(
  source: Headers,
  names: readonly string[],
): Record<string, string> {
  const copied: Record<string, string> = {}
  for (const name of names) {
    const value = source.get(name)
    if (value) copied[name.toLowerCase()] = value
  }
  return copied
}
