import { test, expect } from './fixtures';

/**
 * Chat → Work handoff (approved Builder proposal).
 *
 * An approved Builder job used to dead-end in chat at "Track it in the Work
 * view" with no action. This spec drives the real user control — the "Open in
 * Work" button on the resumed proposal card — through the mounted app at both
 * CI viewports (desktop 1440x900 and iPhone 14), and asserts the app actually
 * lands on the Work surface with the job's row visible.
 *
 * Gateway calls are stubbed because the smoke suite runs the Next server with
 * no Python gateway; fixtures.ts keeps /proxy/health answering so <main>
 * mounts at all. The chat history stub is what the app itself fetches to
 * recover the conversation, exactly like a real reload.
 */

const MISSION_ID = 'conv-smoke-chat-to-work-handoff-1';
const INITIATIVE_ID = 'smoke-init-chat-to-work';
const PACKET_ID = 'smoke-packet-chat-to-work';
const TASK_ID = 'smoke-task-chat-to-work';
const JOB_TITLE = 'Cap the flaky retry loop at max_attempts';

const PROPOSAL_FENCE = [
  'Here is the bounded job. Approve it and Builder will run it.',
  '',
  '```kitty-builder-proposal',
  JSON.stringify({
    objective: JOB_TITLE,
    instructions: 'Cap the retry loop at max_attempts.',
    allowed_paths: ['gateway/'],
    title: JOB_TITLE,
  }),
  '```',
].join('\n');

function validUntil(minutes = 10) {
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

async function stubAppRoutes(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });

  await page.route('**/proxy/api/models', route =>
    route.fulfill({ json: { data: [{ id: 'kitty-default' }] } }),
  );
  await page.route('**/proxy/models/picker', route =>
    route.fulfill({
      json: {
        schema_version: 1,
        source: 'smoke-chat-to-work',
        discovery: { state: 'available', reason: null, checked_at: null },
        claims: { role_tags: 'heuristic', alternatives: 'cost-screened only' },
        presets: [{
          role: 'auto', label: 'Daily Kitty', route: 'kitty-default',
          purpose: 'Everyday use.', kind: 'router', provider: null, model: null,
          configured: true, catalogue: null, catalogue_state: 'not_applicable', alternatives: [],
        }],
      },
    }),
  );
  await page.route('**/proxy/runtime/**', route =>
    route.fulfill({
      json: {
        revision: 'smoke-chat-to-work',
        connections: { gateway: { state: 'available', reason: null } },
        inference: { available_models: { state: 'available', value: ['kitty-default'] } },
        tools: { state: 'available' },
        context: { active_project: { value: null } },
        execution: { builder: { value: null, state: 'available' } },
      },
    }),
  );
  await page.route('**/proxy/onboarding', route =>
    route.fulfill({ json: { onboarded: true } }),
  );

  // A conversation whose assistant reply carries the proposal fence — this is
  // what a page reload sees after a job has been approved.
  await page.route('**/proxy/chats', route =>
    route.fulfill({
      json: { chats: [{ id: 'smoke-handoff-chat', title: 'Handoff', model: 'kitty-default', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }] },
    }),
  );
  await page.route('**/proxy/chats/*/messages', route =>
    route.fulfill({
      json: {
        conversation_id: 'smoke-handoff-chat',
        messages: [
          { id: 'm0', role: 'user', content: 'Fix the flaky retry loop.', created_at: Date.now() / 1000 },
          { id: 'm1', role: 'assistant', content: PROPOSAL_FENCE, model: 'kitty-default', created_at: Date.now() / 1000 + 1 },
        ],
      },
    }),
  );
  await page.route('**/proxy/chats/*/lifecycle', route =>
    route.fulfill({ json: { conversation: {}, turns: [] } }),
  );

  // Chat persists the durable mission id per message; seeding it is exactly
  // the state a reload finds, so the card must render the resumed-job view.
  await page.addInitScript(
    ([key, mission]) => { window.localStorage.setItem(key, mission) },
    [`kitty.builder-proposal.smoke-handoff-chat.1`, MISSION_ID] as const,
  );

  await page.route(`**/proxy/builder/conversation/resume*`, route =>
    route.fulfill({
      json: {
        ok: true,
        state: 'in_progress',
        mission: { id: MISSION_ID, state: 'in_progress' },
        current_work: { packet_id: PACKET_ID, task_id: TASK_ID, state: 'running', attempt_count: 1 },
        blocker: null,
        pr: null,
      },
    }),
  );

  await page.route('**/proxy/builder/supervisor', route =>
    route.fulfill({
      json: {
        schema_version: 1, running: true, active_runs: [], eligible_now: 0, on_hold: 0,
        last_tick_at: validUntil(0), lock_path: null, scheduler_enabled: false,
      },
    }),
  );

  await page.route('**/proxy/work', route =>
    route.fulfill({
      json: {
        schema_version: 1,
        observed_at: validUntil(0),
        valid_until: validUntil(10),
        source: { kind: 'builder', state: 'available', reason: null },
        counts: { total: 1, active: 1, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
        queue: { total: 1, queued: 0, claimed: 0, running: 1, blocked: 0, pr_opened: 0, awaiting_review: 0, done: 0, failed: 0, cancelled: 0 },
        items: [{
          id: INITIATIVE_ID,
          title: JOB_TITLE,
          state: 'active',
          source: { kind: 'builder', initiative_id: INITIATIVE_ID, packet_id: PACKET_ID },
          current_packet: { id: PACKET_ID, title: JOB_TITLE, objective: JOB_TITLE, task_id: TASK_ID, task_state: 'running', updated_at: validUntil(0) },
          current_run: { id: 'smoke-run-1', state: 'running', started_at: validUntil(0), ended_at: null },
          blocker: null,
          next_action: 'claim',
          evidence: {},
          data_quality: { state: 'ok', issues: [] },
          updated_at: validUntil(0),
        }],
        item_limit: 25,
        total_items: 1,
      },
    }),
  );
}

test('chat proposal handoff opens the durable job in Work', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await stubAppRoutes(page);
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });

  // Reach Chat with real user controls: desktop rail button, mobile bottom-nav.
  await page.getByRole('button', { name: 'Chat', exact: true }).first().click();

  // The approved job shows its durable state and the one-click handoff.
  const handoff = page.getByTestId('builder-proposal-open-work');
  await expect(handoff).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(`Mission: ${MISSION_ID}`, { exact: false })).toBeVisible();

  await handoff.click();

  // Work surface mounted, showing the same job's row.
  await expect(page.getByRole('heading', { name: 'Work' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(JOB_TITLE).first()).toBeVisible();

  // No horizontal overflow at this viewport (mobile regression guard).
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `horizontal overflow ${overflow}px at ${testInfo.project.name}`).toBeLessThanOrEqual(0);

  expect(errors, `page errors: ${errors.join(' | ')}`).toEqual([]);
});
