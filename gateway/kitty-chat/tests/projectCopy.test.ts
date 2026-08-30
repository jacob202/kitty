import { describe, expect, it } from 'vitest'
import { projectSummaryCopy, projectNextStepCopy } from '../src/lib/project-copy'
import type { GatewayNextStep, GatewayProject } from '../src/lib/gateway'

function project(overrides: Partial<GatewayProject> = {}): GatewayProject {
  return { kind: 'life', summary: '', ...overrides } as GatewayProject
}

function nextStep(overrides: Partial<GatewayNextStep> = {}): GatewayNextStep {
  return { step: '', why: '', recent_win: '', ...overrides } as GatewayNextStep
}

describe('project copy', () => {
  // Codex P2 on #675: `tracker` was unqualified, so ordinary life-project
  // wording was rewritten into the false claim that nothing is connected.
  it('leaves ordinary life-project wording alone', () => {
    for (const summary of [
      'set up a habit tracker',
      'review sleep tracker results',
      'a budget tracker for groceries',
    ]) {
      expect(projectSummaryCopy(project({ summary }))).toBe(summary)
    }
  })

  it('still replaces internal project-setup wording', () => {
    for (const summary of [
      'Register project paths in the tracker',
      'sync the issue tracker',
      'clone the repo first',
    ]) {
      expect(projectSummaryCopy(project({ summary }))).toBe('No project details are connected yet.')
    }
  })

  it('keeps a life next step intact when it merely mentions a tracker', () => {
    const step = nextStep({
      step: 'Set up the habit tracker for this week',
      why: 'It keeps the streak visible',
      recent_win: 'Logged four days running',
    })
    expect(projectNextStepCopy(project(), step)).toEqual(step)
  })

  it('replaces a next step built from internal project-setup wording', () => {
    const result = projectNextStepCopy(
      project(),
      nextStep({ step: 'Register project paths', why: 'the repo is not linked', recent_win: '' }),
    )
    expect(result.step).toBe('Kitty needs more project context before it can suggest a next step.')
    expect(result.why).not.toMatch(/repo/i)
  })

  it('replaces code-project summaries that expose version-control internals', () => {
    expect(projectSummaryCopy(project({ kind: 'code', summary: 'git status shows a dirty branch' })))
      .toBe('Development work is in progress.')
  })

  it('returns an empty summary unchanged', () => {
    expect(projectSummaryCopy(project({ summary: '   ' }))).toBe('')
  })
})
