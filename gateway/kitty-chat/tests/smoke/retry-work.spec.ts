import { test, expect, type Page } from './fixtures';

/**
 * KPROOF runtime product journey — confirmed "Retry this work" on the Builder
 * surface inside the launched Work UI.
 *
 * The gateway is stubbed at the proxy boundary (same pattern as the rest of
 * the smoke suite). The manifest route serves the packet's durable state, and
 * the /proxy/builder/command route records every mutation so the test can
 * prove: no request before confirmation, cancel sends nothing, confirm sends
 * exactly one requeue for the selected initiative/packet, an {ok:false}
 * rejection is surfaced visibly, mutation acceptance is not completion, and
 * progress phases advance only from refreshed manifest facts.
 */

const INITIATIVE_ID = 'kproof-retry-ui';
const PACKET_ID = 'KPROOF-RETRY-1';
const TASK_ID = 'task-kproof-retry-1';
const TITLE = 'Retry this work journey packet';

const BASE_UPDATED_AT = '2026-08-10T12:00:00Z';

const VALIDATION_ATTEMPT = {
  id: 2,
  number: 2,
  outcome: null,
  counts_toward_budget: true,
  implementation_status: 'completed',
  validation_status: null,
  review_verdict: null,
  implementation: null,
  validation: null,
  review: null,
  lease_id: 1,
  created_at: '2026-08-10T12:00:00Z',
  updated_at: '2026-08-10T12:01:00Z',
  data_quality: { state: 'complete', issues: [] },
};

function packet(
  taskState: string | null,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    initiative_id: INITIATIVE_ID,
    packet_id: PACKET_ID,
    title: TITLE,
    objective: 'Prove the confirmed retry flow from durable facts.',
    task_id: TASK_ID,
    task_state: taskState,
    depends_on: [],
    eligibility: { state: 'not_queued', blocked_by: [] },
    budget: { used: 1, max: 3, exhausted: false },
    attempt_count: 1,
    attempt_history_truncated: false,
    attempt_history: [],
    lease: null,
    run: null,
    publication: null,
    last_event: null,
    failure_kind: null,
    blocked_reason: null,
    last_error: null,
    updated_at: BASE_UPDATED_AT,
    base_sha: 'a'.repeat(40),
    data_quality: { state: 'complete', issues: [] },
    investigation: {
      logs: { state: 'unavailable', reason: 'Safe bounded log delivery is not available yet.' },
      artifacts: { state: 'unavailable', reason: 'Safe durable artifact delivery is not available yet.' },
    },
    ...overrides,
  };
}

/** Failed packet that draws attention and offers Retry this work. */
function failedPacket(updatedAt: string = BASE_UPDATED_AT): Record<string, unknown> {
  return packet('failed', {
    eligibility: { state: 'not_queued', blocked_by: [] },
    failure_kind: 'validation',
    blocked_reason: null,
    last_error: '1 validation command failed (exit 1)',
    run: {
      id: 'run-failed',
      state: 'failed',
      started_at: '2026-08-10T11:58:00Z',
      last_heartbeat_at: '2026-08-10T12:00:00Z',
      ended_at: '2026-08-10T12:00:00Z',
      exit_code: 1,
      updated_at: BASE_UPDATED_AT,
    },
    updated_at: updatedAt,
  });
}

function manifest(builderPacket: unknown): Record<string, unknown> {
  return {
    schema_version: 2,
    manifest_id: 'kproof-retry-manifest',
    revision: 'retry-ui',
    generated_at: '2026-08-10T12:00:00Z',
    valid_until: '2099-08-10T12:05:00Z',
    application: {
      name: 'kitty',
      version: { state: 'available', value: '0.0.0' },
      build_commit: null,
      environment: 'test',
    },
    clock: { state: 'available', value: { current_time: '2026-08-10T12:00:00Z', timezone: 'UTC' } },
    context: {
      active_project: { state: 'available', value: null },
      repository: {
        state: 'available',
        value: { root: '/tmp', branch: 'main', commit: 'a'.repeat(40), dirty: false, changed_paths: 0 },
      },
    },
    execution: {
      builder: {
        state: 'available',
        value: {
          schema_version: 2,
          attempt_history_limit: 10,
          integrity: { state: 'complete', partial_packets: 0, total_packets: 1 },
          queue: {
            total: 1, queued: 0, claimed: 0, running: 0, blocked: 0,
            pr_opened: 0, awaiting_review: 0, done: 0, failed: 1, cancelled: 0,
          },
          initiatives: [
            {
              initiative_id: INITIATIVE_ID,
              title: 'KPROOF retry control journey',
              state: 'failed',
              pause_reason: null,
              next_packet: null,
              counts: {
                total: 1, queued: 0, claimed: 0, running: 0, blocked: 0,
                pr_opened: 0, awaiting_review: 0, done: 0, failed: 1, cancelled: 0, exhausted: 0,
              },
              data_quality: { state: 'complete', partial_packets: 0 },
              created_at: '2026-08-10T11:00:00Z',
              updated_at: '2026-08-10T12:00:00Z',
              packets: [builderPacket],
            },
          ],
        },
      },
    },
    inference: {
      routing_mode: 'auto',
      available_models: { state: 'available', value: [] },
      providers: [],
      execution_location: 'local',
    },
    tools: { state: 'available', value: [] },
    connections: {
      gateway: { state: 'available', value: null },
      litellm: { state: 'available', value: null },
    },
    approvals: { state: 'available', value: null },
  };
}

async function openFailedPacketDetail(page: Page): Promise<void> {
  await page.goto('/');
  await page.getByRole('button', { name: /^work$/i }).first().click();
  await page.getByRole('button', { name: `View packet ${TITLE}` }).click();
  await expect(page.getByRole('button', { name: 'Retry this work' })).toBeVisible();
}

/**
 * The strip always lists every phase chip, so phase assertions must target the
 * active chip (aria-current="step") rather than raw strip text.
 */
function currentPhaseChip(page: Page) {
  return page.getByLabel('Retry progress').locator('[aria-current="step"]');
}

/**
 * Advance the mocked clock in small steps, polling the active phase chip after
 * each step, until it shows the expected phase. Refetch timers are scheduled
 * relative to fetch completion, so fixed jumps are fragile; stepping keeps the
 * real event loop free to settle each manifest fetch before the next jump.
 */
async function advanceUntilPhase(page: Page, phase: string): Promise<void> {
  for (let i = 0; i < 30; i += 1) {
    await page.clock.fastForward('00:05');
    try {
      await expect(currentPhaseChip(page)).toHaveText(phase, { timeout: 500 });
      return;
    } catch {
      // Not reached yet; keep advancing the manifest poll.
    }
  }
  await expect(currentPhaseChip(page)).toHaveText(phase);
}

test.beforeEach(async ({ page }) => {
  // Pre-dismiss onboarding modal
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

test('Retry this work requires inline confirmation; cancel sends no mutation', async ({ page }) => {
  const commandRequests: unknown[] = [];
  await page.route('**/proxy/runtime/manifest', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(manifest(failedPacket())),
    })
  );
  await page.route('**/proxy/builder/command', (route) => {
    commandRequests.push(route.request().postDataJSON());
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, action: 'requeue', task_id: TASK_ID, detail: 'task requeued' }),
    });
  });

  await openFailedPacketDetail(page);

  // First click opens the inline approval preview for the exact selected packet.
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await expect(page.getByLabel('Retry this work preview')).toBeVisible();
  await expect(page.getByLabel('Retry this work preview')).toContainText(INITIATIVE_ID);
  await expect(page.getByLabel('Retry this work preview')).toContainText(PACKET_ID);
  expect(commandRequests).toHaveLength(0);

  // Cancel closes the preview and sends no mutation.
  await page.getByRole('button', { name: 'Cancel retry' }).click();
  await expect(page.getByLabel('Retry this work preview')).toBeHidden();
  expect(commandRequests).toHaveLength(0);

  // Reopening the preview still sends nothing.
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await expect(page.getByLabel('Retry this work preview')).toBeVisible();
  expect(commandRequests).toHaveLength(0);
});

test('confirm retry sends exactly one requeue and progress advances only from manifest facts', async ({ page }) => {
  await page.clock.install();

  let taskState: string = 'failed';
  const commandRequests: Array<{
    action?: string;
    initiative_id?: string;
    packet_id?: string;
    task_id?: string;
  }> = [];

  await page.route('**/proxy/runtime/manifest', (route) => {
    let builderPacket: Record<string, unknown>;
    if (taskState === 'failed') {
      builderPacket = failedPacket();
    } else if (taskState === 'validation') {
      builderPacket = packet('running', {
        eligibility: { state: 'eligible', blocked_by: [] },
        attempt_history: [VALIDATION_ATTEMPT],
        run: {
          id: 'run-2',
          state: 'running',
          started_at: '2026-08-10T12:00:00Z',
          last_heartbeat_at: '2026-08-10T12:01:00Z',
          ended_at: null,
          exit_code: null,
          updated_at: '2026-08-10T12:01:00Z',
        },
      });
    } else if (taskState === 'running') {
      builderPacket = packet('running', {
        eligibility: { state: 'eligible', blocked_by: [] },
        run: {
          id: 'run-2',
          state: 'running',
          started_at: '2026-08-10T12:00:00Z',
          last_heartbeat_at: '2026-08-10T12:01:00Z',
          ended_at: null,
          exit_code: null,
          updated_at: '2026-08-10T12:01:00Z',
        },
      });
    } else if (taskState === 'refailed') {
      // Durable re-failure after the retry: newer updated_at, returns to attention.
      builderPacket = failedPacket('2026-08-10T12:30:00Z');
    } else {
      builderPacket = packet(taskState, { eligibility: { state: 'eligible', blocked_by: [] } });
    }
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(manifest(builderPacket)),
    });
  });

  await page.route('**/proxy/builder/command', async (route) => {
    commandRequests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, action: 'requeue', task_id: TASK_ID, detail: 'task requeued' }),
    });
  });

  await openFailedPacketDetail(page);
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await page.getByRole('button', { name: 'Confirm retry' }).click();

  // Accepted is not complete: the mutation was accepted but the manifest has
  // not reported any durable progress yet. The accepted chip only renders
  // after the mutation's onSuccess, so awaiting it also settles the POST.
  await expect(currentPhaseChip(page)).toHaveText('accepted');
  await expect(currentPhaseChip(page)).not.toHaveText('complete');

  // Exactly one requeue mutation, carrying the selected initiative and packet.
  expect(commandRequests).toHaveLength(1);
  expect(commandRequests[0]).toMatchObject({
    action: 'requeue',
    initiative_id: INITIATIVE_ID,
    packet_id: PACKET_ID,
    task_id: TASK_ID,
  });

  // Durable phase progression, each step driven only by a manifest refresh.
  taskState = 'queued';
  await advanceUntilPhase(page, 'queued');

  taskState = 'running';
  await advanceUntilPhase(page, 'running');

  taskState = 'validation';
  await advanceUntilPhase(page, 'validation');

  taskState = 'awaiting_review';
  await advanceUntilPhase(page, 'review');

  taskState = 'done';
  await advanceUntilPhase(page, 'complete');

  // A durable re-failure after retry returns to attention and never shows complete.
  taskState = 'refailed';
  for (let i = 0; i < 30 && (await page.getByLabel('Retry progress').count()) === 1; i += 1) {
    await page.clock.fastForward('00:05');
  }
  await expect(page.getByLabel('Retry progress')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retry this work' })).toBeVisible();
});

test('an {ok:false} Builder response is surfaced as visible failure, never completion', async ({ page }) => {
  await page.route('**/proxy/runtime/manifest', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(manifest(failedPacket())),
    })
  );
  await page.route('**/proxy/builder/command', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: false,
        action: 'requeue',
        task_id: TASK_ID,
        error: 'task not found: requeue rejected',
      }),
    })
  );

  await openFailedPacketDetail(page);
  await page.getByRole('button', { name: 'Retry this work' }).click();
  await page.getByRole('button', { name: 'Confirm retry' }).click();

  await expect(page.getByText(/task not found: requeue rejected/)).toBeVisible();
  await expect(page.getByText(/Retry accepted/)).toHaveCount(0);
  // The retry action remains available and no progress claims completion.
  await expect(page.getByRole('button', { name: 'Retry this work' })).toBeVisible();
  await expect(page.getByLabel('Retry progress')).toHaveCount(0);
});
