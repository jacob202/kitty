import { afterEach, beforeEach, expect, vi, type MockInstance } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'

expect.extend(matchers)

Element.prototype.scrollIntoView = () => {}

function createMemoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() { return values.size },
    clear: () => values.clear(),
    getItem: (key) => values.get(String(key)) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => { values.delete(String(key)) },
    setItem: (key, value) => { values.set(String(key), String(value)) },
  }
}

// Node 26 exposes an experimental localStorage getter that Vitest leaves ahead
// of jsdom's browser storage. Replace it so frontend tests exercise browser-like
// storage semantics instead of warning and silently falling back.
const testLocalStorage = createMemoryStorage()
Object.defineProperty(window, 'localStorage', { configurable: true, value: testLocalStorage })

let consoleErrorSpy: MockInstance

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', { configurable: true, value: testLocalStorage })
  testLocalStorage.clear()

  // React reports invalid DOM, hydration mismatches, and render-time failures via
  // console.error. A test that expects an error must explicitly own/mock it.
  consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    throw new Error(`Unexpected console.error: ${args.map(String).join(' ')}`)
  })
})

afterEach(() => {
  consoleErrorSpy.mockRestore()
})
