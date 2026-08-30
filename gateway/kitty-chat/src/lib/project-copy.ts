import type { GatewayNextStep, GatewayProject } from '@/lib/gateway'

const CODE_INTERNAL_COPY = /(?:\bgit\s+(?:status|diff)\b|\bbranch\b|\bdirty\b|memory mention|\brepo\b)/i
// `tracker` was unqualified, so ordinary life-project content — "set up a
// habit tracker", "review sleep tracker results" — was rewritten into the
// false claim that no project details are connected. Only the internal
// project/issue tracker counts here.
const PROJECT_SETUP_INTERNAL_COPY = /(?:register(?:ing)?\b.*\bpaths?\b|\bproject paths?\b|\b(?:project|issue|builder)\s+tracker\b|\brepo\b)/i

export function projectSummaryCopy(project: GatewayProject): string {
  const summary = project.summary?.trim() ?? ''
  if (!summary) return ''
  if (project.kind === 'code' && CODE_INTERNAL_COPY.test(summary)) return 'Development work is in progress.'
  if (PROJECT_SETUP_INTERNAL_COPY.test(summary)) return 'No project details are connected yet.'
  return summary
}

export function projectNextStepCopy(project: GatewayProject, nextStep: GatewayNextStep): GatewayNextStep {
  const raw = `${nextStep.step} ${nextStep.why} ${nextStep.recent_win}`
  if (project.kind === 'code' && CODE_INTERNAL_COPY.test(raw)) {
    return {
      ...nextStep,
      step: 'Review the work already in progress before making more changes.',
      why: 'This avoids overwriting work that is already underway.',
      recent_win: 'There is already work in progress to continue from.',
    }
  }
  if (PROJECT_SETUP_INTERNAL_COPY.test(raw)) {
    return {
      ...nextStep,
      step: 'Kitty needs more project context before it can suggest a next step.',
      why: 'More project information needs to be connected first.',
      recent_win: '',
    }
  }
  return nextStep
}
