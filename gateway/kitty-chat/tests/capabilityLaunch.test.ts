import { describe, expect, it } from 'vitest'

import { composeSkillLaunchInput } from '../src/lib/capability-launch'

describe('composeSkillLaunchInput', () => {
  it('preserves an existing composer draft when a skill is selected', () => {
    expect(composeSkillLaunchInput('Please review this carefully', 'verified-delivery')).toBe(
      'Use skill: verified-delivery\n\nPlease review this carefully',
    )
  })

  it('creates only the directive when the composer is empty', () => {
    expect(composeSkillLaunchInput('', 'verified-delivery')).toBe('Use skill: verified-delivery\n\n')
  })
})
