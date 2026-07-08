import { describe, it, expect } from 'vitest';
import { evaluateNextAction } from './ranking';
import type { GatewayAction, GatewayTriageEntry, GatewayNextStep, GatewayTodo, GatewayHealthPayload, GatewayDeadline } from './gateway';

describe('evaluateNextAction', () => {
  const healthyGateway: GatewayHealthPayload = { ok: true, litellmReachable: true, error: null };
  const unhealthyGateway: GatewayHealthPayload = { ok: false, litellmReachable: false, error: 'down' };

  it('returns null when no inputs are provided', () => {
    expect(evaluateNextAction()).toBeNull();
  });

  it('prioritizes critical deadlines over other actions', () => {
    const deadlines: GatewayDeadline[] = [{
      id: 1, project_id: 1, source: 'sys', source_id: null, due_date: '2026-07-09',
      obligation: 'Submit taxes', amount: null, currency: null,
      confidence: 'high', status: 'open', created_at: 0, updated_at: 0, pushed_at: null,
    }];
    const todos: GatewayTodo[] = [{ id: 1, content: 'Buy milk', status: 'pending' }];

    const result = evaluateNextAction([], [], [], todos, healthyGateway, deadlines);
    expect(result?.kind).toBe('deadline');
    expect(result?.title).toBe('Submit taxes');
  });

  it('prioritizes needs-jacob over proposed actions', () => {
    const needsJacob: GatewayTriageEntry[] = [{
      inbox_id: '1', ts: 1, bucket: 'needs_jacob', confidence: 0.9, rationale: 'urgent', text: 'Important decision', created_at: 'now'
    }];
    const actions: GatewayAction[] = [{
      id: 1, created_at: 'now', source_kind: 'sys', source_id: null, kind: 'action', title: 'Approve PR',
      preview: '', payload: {}, risk_tier: 'T1', status: 'pending', result: null, decided_at: null, executed_at: null
    }];

    const result = evaluateNextAction(actions, needsJacob, [], [], healthyGateway, []);
    expect(result?.kind).toBe('needs_jacob');
    expect(result?.title).toBe('Important decision');
  });

  it('returns gateway_error if the top action is AI dependent and gateway is down', () => {
    const needsJacob: GatewayTriageEntry[] = [{
      inbox_id: '1', ts: 1, bucket: 'needs_jacob', confidence: 0.9, rationale: 'urgent', text: 'Important decision', created_at: 'now'
    }];

    const result = evaluateNextAction([], needsJacob, [], [], unhealthyGateway, []);
    expect(result?.kind).toBe('gateway_error');
    expect(result?.title).toBe('gateway offline — fix required');
    expect(result?.reason).toBe('Important decision'); // The reason shows what is blocked
  });

  it('does not return gateway_error if the top action is NOT AI dependent, even if gateway is down', () => {
    const deadlines: GatewayDeadline[] = [{
      id: 1, project_id: 1, source: 'sys', source_id: null, due_date: '2026-07-09',
      obligation: 'Submit taxes', amount: null, currency: null,
      confidence: 'high', status: 'open', created_at: 0, updated_at: 0, pushed_at: null,
    }];

    const result = evaluateNextAction([], [], [], [], unhealthyGateway, deadlines);
    expect(result?.kind).toBe('deadline');
    expect(result?.title).toBe('Submit taxes');
  });
});
