import { describe, expect, it } from 'vitest'
import { AgentWorkspacePanel } from '../src/components/AgentWorkspacePanel'
import { REDIRECTS, VIEWS, getView } from '../src/lib/views'

describe('view registry', () => {
  it('maps Agents to the real Global Agent Room panel', () => {
    expect(VIEWS.agents.component).toBe(AgentWorkspacePanel)
  })

  it('preserves the Research registry entry from PR #735', () => {
    expect(getView('research')?.title).toBe('Research')
  })
})

describe('view redirects', () => {
  it('redirects ordinary Builder navigation to Work', () => {
    expect(REDIRECTS.builder).toBe('work')
  })

  it('keeps deep Builder evidence as an explicit secondary surface', () => {
    expect(getView('builder-details')?.title).toBe('Builder details')
    expect(REDIRECTS['builder-details']).toBeUndefined()
  })

  it('keeps Automations as a first-class surface', () => {
    expect(getView('automations')?.title).toBe('Automations')
    expect(REDIRECTS.automations).toBeUndefined()
  })

  it('keeps Tasks as a dedicated secondary surface', () => {
    expect(REDIRECTS.tasks).toBeUndefined()
  })

  it('does not redirect Projects away from itself', () => {
    // Rail's primary nav, Home's "open projects" actions, and Cmd-K's
    // "projects" command all navigate to this id expecting ProjectsView.
    // A redirect here silently sends every one of those to Library instead
    // — Library has no Projects content, so the destination is just wrong.
    expect(REDIRECTS.projects).toBe('projects')
  })
})
