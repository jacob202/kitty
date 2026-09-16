import { act } from 'react'
import { describe, expect, it } from 'vitest'

// Guards a failure mode that is invisible until an entire suite goes red.
// Vitest only defaults NODE_ENV when it is unset, so a developer shell that
// exports NODE_ENV=production makes `react` resolve its production build — which
// does not export `act`. Every @testing-library/react render then throws
// "React.act is not a function", and 800+ UI tests fail for a reason that has
// nothing to do with the code under test.
describe('test environment', () => {
  it('pins NODE_ENV instead of inheriting it from the shell', () => {
    expect(process.env.NODE_ENV).toBe('test')
  })

  it('loads a React build that exposes act', () => {
    expect(typeof act).toBe('function')
  })
})
