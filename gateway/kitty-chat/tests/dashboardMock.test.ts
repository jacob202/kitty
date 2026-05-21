import { describe, expect, it } from 'vitest'
import {
  commandZones,
  contextFound,
  continueItems,
  insights,
  nowItems,
  realityCheck,
  signals,
  suggestedFix,
} from '../src/lib/dashboardMock'

describe('dashboardMock', () => {
  it('covers the dashboard home zones', () => {
    expect(nowItems.length).toBeGreaterThan(0)
    expect(continueItems.length).toBeGreaterThan(0)
    expect(signals.length).toBeGreaterThan(0)
    expect(commandZones.length).toBeGreaterThanOrEqual(4)
    expect(insights.length).toBeGreaterThan(0)
    expect(contextFound.length).toBeGreaterThan(0)
  })

  it('includes a fix card and reality check tone states', () => {
    expect(suggestedFix.title).toBeTruthy()
    expect(suggestedFix.action).toBeTruthy()
    expect(realityCheck.tones.map(tone => tone.id)).toEqual(['gentle', 'direct'])
  })
})
