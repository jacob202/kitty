// Translates a thrown fetch/query error into one short, plain-language
// sentence. Jacob does not code — raw strings like "Gateway returned 404
// Not Found" name no cause and no action. This is the only place that
// translation happens; gateway.ts keeps returning the raw diagnostic form
// for anything that still needs it.

function extractParts(error: unknown): { message: string; name: string } {
  // DOMException (e.g. AbortError from fetch's AbortController) does not
  // extend Error but carries the same name/message shape, so duck-type it.
  if (error instanceof Error || (error && typeof error === 'object' && 'message' in error && 'name' in error)) {
    const withParts = error as { message?: unknown; name?: unknown }
    return {
      message: typeof withParts.message === 'string' ? withParts.message : '',
      name: typeof withParts.name === 'string' ? withParts.name : '',
    }
  }
  if (typeof error === 'string') {
    return { message: error, name: '' }
  }
  return { message: '', name: '' }
}

export function describeFailure(error: unknown): string {
  const { message, name } = extractParts(error)

  const gatewayStatus = message.match(/^Gateway returned (\d{3})\b/)
  if (gatewayStatus) {
    const status = Number(gatewayStatus[1])
    if (status === 404) return "Kitty is running but this part isn't answering yet."
    if (status === 401 || status === 403) return 'Kitty refused the request — check the gateway secret in Settings.'
    if (status >= 500 && status <= 599) return "Kitty's service hit an error. Try again in a moment."
    if (status >= 400 && status <= 499) return "Kitty couldn't complete that request."
  }

  if (name === 'AbortError' || /timed out|AbortError/i.test(message)) {
    return 'Kitty took too long to answer. Try again.'
  }

  if (/failed to fetch|networkerror|load failed|network error/i.test(message)) {
    return "Can't reach Kitty — check that it's running."
  }

  return 'Something went wrong reaching Kitty.'
}
