import { test, expect, type Page } from './fixtures';

/**
 * KPROOF Retry-this-work — launched Work UI journey with browser-bound
 * deterministic Gateway facts.
 *
 * The Next server runs alone (no Python gateway), so every backend response is
 * stubbed at the browser boundary. No provider/Builder work is dispatched.
 *
 * Proves the confirmation contract end to end:
 *  1. failed work shows `Retry this work`, not raw `requeue`;
 *  2. the first click opens an inline preview and sends zero action requests;
 *  3. Cancel sends zero;
 *  4. Confirm sends exactly one requeue POST keyed to the selected packet;
 *  5. `{ok:false}` is a visible failure;
 *  6. `{ok:true}` is accepted/waiting, never complete;
 *  7. refreshed manifests drive queued → running → validation → review → done
 *     and the UI follows;
 *  8. an unchanged manifest after acceptance never claims completion.
 */

const INITIATIVE_ID = 'kproof-retry-initiative';
const PACKET_ID = 'KPROOF-RETRY-1';
const TASK_ID = 'task-kproof-retry-1';
const TITLE = 'Retry contract smoke packet';

type DurablePhase = 'failed' | 'queued' | 'running' | 'validation' | 'review' | 'done';

// Durable facts served by the runtime-manifest stub. The test advances this
// exactly as a real gateway would between snapshots.
let durablePhase: DurablePhase = 'failed';

function recentIso(): string {
  return new Date().toISOString();
}

function attemptFor(phase: DurablePhase) {
  const base = {
    id: 2,
    number: 2,
    outcome: null,
    counts_toward_budget: false,
    implementation_status: null,
    validation_status: null,
    review_verdict: null,
    implementation: null,
    validation: null,
    review: null,
    lease_id: 7,
    created_at: recentIso(),
    updated_at: recentIso(),
    data_quality: { state: 'complete', issues: [] },
  };
  if (phase === 'validation' || phase === 'review') {
    return {
      ...base,
      validation_status: 'passed',
      validation: {
        status: 'passed',
        command_count: 2,
        failed_command_count: 0,
        summary: '2 validation commands passed.',
      },
    };
  }
  return base;
}

function packetFor(phase: DurablePhase) {
  const stateByPhase: Record<DurablePhase, string> = {
    failed: 'failed',
    queued: 'queued',
    running: 'running',
    validation: 'running',
    review: 'awaiting_review',
    done: 'done',
  };
  const recent = recentIso();
  const failed = phase === 'failed';
  return {
    initiative_id: INITIATIVE_ID,
    packet_id: PACKET_ID,
    title: TITLE,
    objective: 'Prove the confirmed retry flow end to end.',
    task_id: TASK_ID,
    task_state: stateByPhase[phase],
    depends_on: [],
    eligibility: {
      state: failed ? 'blocked' : 'eligible',
      blocked_by: failed ? ['KPROOF-PREV'] : [],
    },
    budget: { used: 1, max: 2, exhausted: false },
    attempt_count: 2,
    attempt_history_truncated: false,
    attempt_history: [
      attemptFor(phase),
      {
        id: 1,
        number: 1,
        outcome: 'failed',
        counts_toward_budget: true,
        implementation_status: 'completed',
        validation_status: 'failed',
        review_verdict: 'reject',
        implementation: { status: 'completed', summary: 'Implemented.', diff_summary: 'Bounded diff.' },
        validation: { status: 'failed', command_count: 1, failed_command_count: 1, summary: '1 validation command failed (exit 1).' },
        review: { verdict: 'reject', summary: 'Evidence needs another look.', findings: [], findings_truncated: false },
        lease_id: null,
        created_at: recent,
        updated_at: recent,
        data_quality: { state: 'complete', issues: [] },
      },
    ],
    lease: failed
      ? null
      : { id: 7, worker_id: 'worker-kproof', branch: 'feat/kproof-retry', base_sha: 'a'.repeat(40), created_at: recent },
    run: failed
      ? { id: 'run-failed', state: 'failed', started_at: recent, last_heartbeat_at: recent, ended_at: recent, exit_code: 1, updated_at: recent }
      : { id: 'run-active', state: phase === 'done' ? 'succeeded' : 'running', started_at: recent, last_heartbeat_at: recent, ended_at: phase === 'done' ? recent : null, exit_code: phase === 'done' ? 0 : null, updated_at: recent },
    publication: null,
    last_event: failed
      ? { id: 10, type: 'infrastructure_failed', created_at: recent, reason: 'worker exited before validation', counts_toward_budget: false }
      : { id: 11, type: 'requeued', created_at: recent, reason: 'retried from the Builder surface', counts_toward_budget: false },
    failure_kind: failed ? 'infrastructure' : null,
    blocked_reason: failed ? 'worker failed' : null,
    last_error: failed ? 'worker exited before validation' : null,
    updated_at: recent,
    base_sha: 'a'.repeat(40),
    data_quality: { state: 'complete', issues: [] },
    investigation: {
      logs: { state: 'unavailable', reason: 'Safe bounded log delivery is not available yet.' },
      artifacts: { state: 'unavailable', reason: 'Safe durable artifact delivery is not available yet.' },
    },
  };
}

function snapshotFor(phase: DurablePhase) {
  const failed = phase === 'failed';
  const done = phase === 'done';
  const queue = {
    total: 1,
    queued: phase === 'queued' ? 1 : 0,
    claimed: 0,
    running: phase === 'running' || phase === 'validation' ? 1 : 0,
    blocked: failed ? 1 : 0,
    pr_opened: 0,
    awaiting_review: phase === 'review' ? 1 : 0,
    done: done ? 1 : 0,
    failed: failed ? 1 : 0,
    cancelled: 0,
  };
  return {
    schema_version: 2,
    attempt_history_limit: 10,
    integrity: { state: 'complete', partial_packets: 0, total_packets: 1 },
    queue,
    initiatives: [
      {
        initiative_id: INITIATIVE_ID,
        title: 'KPROOF retry initiative',
        state: failed ? 'failed' : done ? 'completed' : 'active',
        pause_reason: null,
        next_packet: null,
        counts: { ...queue, exhausted: 0 },
        data_quality: { state: 'complete', partial_packets: 0 },
        created_at: recentIso(),
        updated_at: recentIso(),
        packets: [packetFor(phase)],
      },
    ],
  };
}

function buildManifest() {
  const now = recentIso();
  const validUntil = new Date(Date.now() + 120_000).toISOString();
  const fact = (value: unknown) => ({
    state: 'available',
    value,
    source: 'builder_status',
    observed_at: now,
    valid_until: validUntil,
  });
  return {
    schema_version: 1,
    manifest_id: 'kproof-retry-manifest',
    revision: 'kproof-retry',
    generated_at: now,
    valid_until: validUntil,
    application: {
      name: 'kitty',
      version: fact('test'),
      build_commit: null,
      environment: 'test',
    },
    clock: fact({ current_time: now, timezone: 'UTC' }),
    context: {
      active_project: fact(null),
      repository: fact({ root: '/tmp', branch: 'main', commit: 'x'.repeat(40), dirty: false, changed_paths: 0 }),
    },
    execution: {
      builder: fact(snapshotFor(durablePhase)),
    },
    inference: {
      routing_mode: 'default',
      available_models: fact(['kitty-default']),
      providers: [],
      execution_location: 'local',
    },
    tools: fact([]),
    connections: {
      gateway: fact({ ok: true }),
      litellm: fact({}),
    },
    approvals: fact({}),
  };
}

/** Stub the endpoints the Work view touches and record action requests. */
async function stubGateway(page: Page, opts: { rejectRetry?: boolean } = {}) {
  const actionRequests: Array<Record<string, unknown>> = [];

  await page.route('**/proxy/api/models', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [{ id: 'kitty-default' }] }) }),
  );
  await page.route('**/proxy/runtime/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(buildManifest()) }),
  );
  await page.route('**/proxy/todos', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ todos: [] }) }),
  );
  await page.route('**/proxy/tasks*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tasks: [] }) }),
  );
  await page.route('**/proxy/builder/command', async (route) => {
    const body = route.request().postDataJSON();
    if (body && typeof body === 'object') {
      actionRequests.push(body as Record<string, unknown>);
    }
    const payload = opts.rejectRetry
      ? { ok: false, action: 'requeue', task_id: TASK_ID, error: `task not found: ${PACKET_ID}` }
      : { ok: true, action: 'requeue', task_id: TASK_ID, detail: `task ${TASK_ID} requeued` };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  return actionRequests;
}

/** Navigate to Work and open the failed packet in the embedded Builder surface. */
async function openFailedPacket(page: Page) {
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: /^work$/i }).click();
  await page.getByRole('button', { name: `View packet ${TITLE}` }).click();
  await expect(page.getByRole('button', { name: 'Retry this work' })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
  durablePhase = 'failed';
});

test('failed work shows Retry this work; preview and Cancel send no mutation', async ({ page }) => {
  const actionRequests = await stubGateway(page);

  await openFailedPacket(page);

  // 1. The primary recovery action is `Retry this work`, never raw `requeue`.
  await expect(page.getByRole('button', { name: 'Retry this work' })).toBeVisible();
  expect(await page.getByRole('button', { name: /^requeue$/i }).count()).toBe(0);

  // 2. First click opens the inline preview and performs no mutation.
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await expect(page.getByText(/Retry contract smoke packet \(KPROOF-RETRY-1\)/)).toBeVisible();
  await expect(page.getByText(/completion is reported only when refreshed durable evidence shows it/)).toBeVisible();
  expect(actionRequests).toEqual([]);

  // 3. Cancel closes the preview and still performs no mutation.
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('button', { name: 'Confirm retry' })).toHaveCount(0);
  expect(actionRequests).toEqual([]);
});

test('Confirm retry sends exactly one requeue request; rejection is visible failure', async ({ page }) => {
  const actionRequests = await stubGateway(page, { rejectRetry: true });

  await openFailedPacket(page);
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await page.getByRole('button', { name: 'Confirm retry' }).click();

  // 4. Exactly one requeue POST keyed to the selected packet.
  await expect.poll(() => actionRequests.length).toBe(1);
  expect(actionRequests[0]).toMatchObject({
    action: 'requeue',
    initiative_id: INITIATIVE_ID,
    packet_id: PACKET_ID,
    task_id: TASK_ID,
    reason: 'Builder surface requested requeue',
  });

  // 5. `{ok:false}` is surfaced as a visible failure and the action remains available.
  await expect(page.getByRole('alert')).toContainText('Retry was rejected: task not found: KPROOF-RETRY-1');
  await expect(page.getByRole('button', { name: 'Retry this work' })).toBeVisible();
});

test('accepted retry is waiting, never complete, and unchanged durable facts never claim completion', async ({ page }) => {
  const actionRequests = await stubGateway(page);

  await openFailedPacket(page);
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await page.getByRole('button', { name: 'Confirm retry' }).click();

  // 6. `{ok:true}` means accepted/waiting only.
  await expect(page.getByText(/Retry accepted — waiting for the next durable snapshot/)).toBeVisible();
  await expect(page.getByLabelText('Retry progress')).toHaveCount(0);
  await expect(page.getByText('complete')).toHaveCount(0);

  // 8. The manifest refreshes but the durable packet is unchanged (still failed):
  // the dead copy returns to attention and completion is never claimed.
  await expect.poll(() => actionRequests.length).toBe(1);
  await expect(page.getByText(/This packet failed or was cancelled/)).toBeVisible();
  await expect(page.getByText(/Retry accepted — waiting for the next durable snapshot/)).toBeVisible();
  await expect(page.getByLabelText('Retry progress')).toHaveCount(0);
  await expect(page.getByText('complete')).toHaveCount(0);
});

const RETRY_PHASES: DurablePhase[] = ['queued', 'running', 'validation', 'review', 'done'];

for (const phase of RETRY_PHASES) {
  test(`refreshed durable facts drive the ${phase} retry phase`, async ({ page }) => {
    const actionRequests = await stubGateway(page);

    await openFailedPacket(page);
    await page.getByRole('button', { name: 'Retry this work' }).click();

    // Advance the durable snapshot before confirming; the confirm triggers an
    // authoritative runtime-manifest refresh that serves the new facts.
    durablePhase = phase;
    await page.getByRole('button', { name: 'Confirm retry' }).click();

    const expectedLabel = phase === 'done' ? 'complete' : phase;
    await expect(page.getByLabelText('Retry progress')).toContainText(expectedLabel, { timeout: 10_000 });
    await expect.poll(() => actionRequests.length).toBe(1);
  });
}
