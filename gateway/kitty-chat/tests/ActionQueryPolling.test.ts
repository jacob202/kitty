import { describe, expect, it } from 'vitest'

import { actionRefetchInterval } from '../src/lib/queries'

describe('actionRefetchInterval', () => {
  it.each(['executed', 'failed', 'rejected', 'unknown'])(
    'stops polling terminal %s actions',
    (status) => expect(actionRefetchInterval(status)).toBe(false),
  )

  it.each(['proposed', 'approved', 'executing', undefined])(
    'keeps polling nonterminal %s actions',
    (status) => expect(actionRefetchInterval(status)).toBe(5_000),
  )
})
