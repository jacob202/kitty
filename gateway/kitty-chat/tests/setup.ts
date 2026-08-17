import { afterEach, beforeEach, expect, vi } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'

expect.extend(matchers)

Element.prototype.scrollIntoView = () => {}

// React reports invalid DOM, hydration mismatches, and render-time failures via
// console.error. A test that emits one of those errors is not green unless the
// test explicitly owns and suppresses that console.error call.
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    throw new Error(`Unexpected console.error: ${args.map(String).join(' ')}`)
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})
