import { describe, expect, it } from 'vitest'
import { describeFailure } from '../src/lib/failure-copy'

describe('describeFailure', () => {
  it('maps a 404 Gateway error to a plain-language "not answering yet" message', () => {
    const result = describeFailure(new Error('Gateway returned 404 Not Found'))
    expect(result).toBe("Kitty is running but this part isn't answering yet.")
  })

  it('never leaks the raw status or "Gateway returned" text', () => {
    const result = describeFailure(new Error('Gateway returned 404 Not Found'))
    expect(result).not.toContain('404')
    expect(result).not.toContain('Gateway returned')
  })

  it('maps a 401 Gateway error to a secret-check message', () => {
    const result = describeFailure(new Error('Gateway returned 401 Unauthorized'))
    expect(result).toBe('Kitty refused the request — check the gateway secret in Settings.')
    expect(result).not.toContain('401')
  })

  it('maps a 403 Gateway error to a secret-check message', () => {
    const result = describeFailure(new Error('Gateway returned 403 Forbidden'))
    expect(result).toBe('Kitty refused the request — check the gateway secret in Settings.')
    expect(result).not.toContain('403')
  })

  it('maps a 500 Gateway error to a service-error message', () => {
    const result = describeFailure(new Error('Gateway returned 500 Internal Server Error'))
    expect(result).toBe("Kitty's service hit an error. Try again in a moment.")
    expect(result).not.toContain('500')
  })

  it('maps a 503 Gateway error to a service-error message', () => {
    const result = describeFailure(new Error('Gateway returned 503 Service Unavailable'))
    expect(result).toBe("Kitty's service hit an error. Try again in a moment.")
  })

  it('maps another 4xx Gateway error to a generic "could not complete" message', () => {
    const result = describeFailure(new Error('Gateway returned 429 Too Many Requests'))
    expect(result).toBe("Kitty couldn't complete that request.")
    expect(result).not.toContain('429')
  })

  it('maps a timeout message to a "took too long" message', () => {
    const result = describeFailure(new Error('Request timed out — is the Kitty gateway running?'))
    expect(result).toBe('Kitty took too long to answer. Try again.')
  })

  it('maps an AbortError by name to a "took too long" message', () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    const result = describeFailure(abortError)
    expect(result).toBe('Kitty took too long to answer. Try again.')
  })

  it('maps "failed to fetch" to a network-reachability message', () => {
    const result = describeFailure(new TypeError('Failed to fetch'))
    expect(result).toBe("Can't reach Kitty — check that it's running.")
  })

  it('maps "NetworkError" to a network-reachability message', () => {
    const result = describeFailure(new Error('NetworkError when attempting to fetch resource.'))
    expect(result).toBe("Can't reach Kitty — check that it's running.")
  })

  it('maps "Load failed" (Safari) to a network-reachability message', () => {
    const result = describeFailure(new Error('Load failed'))
    expect(result).toBe("Can't reach Kitty — check that it's running.")
  })

  it('falls back to a generic message for an unrecognized Error', () => {
    const result = describeFailure(new Error('some unexpected internal detail'))
    expect(result).toBe('Something went wrong reaching Kitty.')
  })

  it('falls back to a generic message for a non-Error value', () => {
    const result = describeFailure('a raw string thrown directly')
    expect(result).toBe('Something went wrong reaching Kitty.')
  })

  it('falls back to a generic message for undefined', () => {
    const result = describeFailure(undefined)
    expect(result).toBe('Something went wrong reaching Kitty.')
  })

  it('falls back to a generic message for an empty Error message', () => {
    const result = describeFailure(new Error(''))
    expect(result).toBe('Something went wrong reaching Kitty.')
  })

  it('never returns the raw error message verbatim', () => {
    const raw = 'some unexpected internal detail'
    const result = describeFailure(new Error(raw))
    expect(result).not.toBe(raw)
  })
})
