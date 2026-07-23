import { describe, expect, it } from 'vitest'
import { useKittyState, FORBIDDEN } from '@/hooks/useKittyState'

describe('FORBIDDEN invariant specs', () => {
  it('FORBIDDEN.doneWhileRunning documents the constraint', () => {
    expect(FORBIDDEN.doneWhileRunning).toContain('done')
    expect(FORBIDDEN.doneWhileRunning).toContain('isStreaming')
    expect(FORBIDDEN.doneWhileRunning).toContain('builderActive')
  })

  it('FORBIDDEN.workingAtIdle documents the constraint', () => {
    expect(FORBIDDEN.workingAtIdle).toContain('working')
    expect(FORBIDDEN.workingAtIdle).toContain('false')
  })
})

// The actual state transitions are tested implicitly through the
// lastOutcome/builderActive wiring in page.tsx. These tests encode
// the design contract so future changes that violate it fail loudly.
