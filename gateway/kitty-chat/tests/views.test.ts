import { describe, expect, it } from 'vitest'
import { REDIRECTS } from '../src/lib/views'

describe('view redirects', () => {
  it('redirects ordinary Builder navigation to Work', () => {
    expect(REDIRECTS.builder).toBe('work')
  })

  it('does not redirect Projects away from itself', () => {
    // Rail's primary nav, Home's "open projects" actions, and Cmd-K's
    // "projects" command all navigate to this id expecting ProjectsView.
    // A redirect here silently sends every one of those to Library instead
    // — Library has no Projects content, so the destination is just wrong.
    expect(REDIRECTS.projects).toBe('projects')
  })
})
