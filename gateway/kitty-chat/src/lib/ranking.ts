import type {
  GatewayAction,
  GatewayTriageEntry,
  GatewayNextStep,
  GatewayTodo,
  GatewayHealthPayload,
  GatewayDeadline,
} from './gateway';

export interface RankedAction {
  kind: 'deadline' | 'gateway_error' | 'needs_jacob' | 'proposed_action' | 'project_step' | 'todo';
  title: string;
  preview?: string;
  reason: string;
  targetView?: string;
  sourceId?: string | number;
  score: number;
  blockedBy?: string;
  payload?: unknown;
}

export function evaluateNextAction(
  actions: GatewayAction[] = [],
  needsJacob: GatewayTriageEntry[] = [],
  steps: (GatewayNextStep | null)[] = [],
  todos: GatewayTodo[] = [],
  health: GatewayHealthPayload = { ok: true, litellmReachable: true, error: null },
  deadlines: GatewayDeadline[] = [],
): RankedAction | null {
  let topHumanAction: RankedAction | null = null;

  // 1. Critical Deadlines
  if (deadlines.length > 0) {
    const openDeadlines = deadlines.filter((d) => d.status === 'open' || d.status === 'needs_jacob');
    if (openDeadlines.length > 0) {
      // Sort by earliest due date
      const sorted = [...openDeadlines].sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
      const d = sorted[0];
      topHumanAction = {
        kind: 'deadline',
        title: d.obligation,
        preview: `Due: ${d.due_date}`,
        reason: 'critical deadline',
        sourceId: d.id,
        score: 100,
        payload: d,
      };
    }
  }

  // 2. High Confidence Needs-Jacob
  if (!topHumanAction && needsJacob.length > 0) {
    const sorted = [...needsJacob].sort((a, b) => b.confidence - a.confidence);
    const entry = sorted[0];
    topHumanAction = {
      kind: 'needs_jacob',
      title: entry.text?.slice(0, 140) || 'an inbox entry needs a decision',
      preview: entry.rationale,
      reason: `needs a decision · ${Math.round(entry.confidence * 100)}% confident`,
      sourceId: entry.inbox_id,
      score: 90,
      payload: entry,
    };
  }

  // 3. Proposed Actions
  if (!topHumanAction && actions.length > 0) {
    const action = actions[0];
    topHumanAction = {
      kind: 'proposed_action',
      title: action.title,
      preview: action.preview,
      reason: `waiting on your approval · ${action.kind} · ${action.risk_tier}`,
      sourceId: action.id,
      score: 80,
      payload: action,
    };
  }

  // 4. Project Next Steps
  if (!topHumanAction) {
    let bestStep: GatewayNextStep | null = null;
    for (const s of steps) {
      if (s && (!bestStep || s.generated_at > bestStep.generated_at)) bestStep = s;
    }
    if (bestStep) {
      topHumanAction = {
        kind: 'project_step',
        title: bestStep.step,
        preview: bestStep.why,
        reason: bestStep.why ? `why: ${bestStep.why}` : 'project next step',
        targetView: 'projects',
        sourceId: bestStep.project_id,
        score: 70,
        payload: bestStep,
      };
    }
  }

  // 5. Open Todos
  if (!topHumanAction) {
    const openTodos = todos.filter((t) => t.status === 'pending' || t.status === 'active');
    if (openTodos.length > 0) {
      const todo = openTodos[0];
      topHumanAction = {
        kind: 'todo',
        title: todo.content,
        reason: "top of today's list — nothing louder is waiting",
        targetView: 'tasks',
        sourceId: todo.id,
        score: 60,
        payload: todo,
      };
    }
  }

  // Evaluate blocking gateway health
  if (topHumanAction) {
    const isAiDependent = ['needs_jacob', 'proposed_action', 'project_step'].includes(topHumanAction.kind);
    if (isAiDependent && (!health.ok || !health.litellmReachable)) {
      return {
        kind: 'gateway_error',
        title: 'gateway offline — fix required',
        preview: 'AI-dependent tasks are blocked until the gateway is reachable.',
        reason: topHumanAction.title,
        blockedBy: health.error || 'Gateway/LiteLLM unreachable',
        score: 110, // Overrides the human action
      };
    }
  }

  return topHumanAction;
}
