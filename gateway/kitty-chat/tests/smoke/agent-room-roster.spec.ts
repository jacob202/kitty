import { test, expect } from './fixtures';

/**
 * Agent Room roster is derived from the live room response, not a hardcoded
 * copy. The panel used to carry its own CANONICAL_AGENTS list, which had
 * already gone stale (it omitted DSH, and later the new `commandcode`
 * participant), so newer senders rendered as bare ids and could not be chosen
 * as direct-message recipients.
 *
 * Agents is reached through the mobile More overflow (added in #766), so this
 * runs on the mobile project; the desktop rail has no Agents destination.
 */

const ROSTER = [
  { id: 'chatgpt', display_name: 'ChatGPT', role: 'external', model: null, status: 'registered' },
  { id: 'claude', display_name: 'Claude', role: 'external', model: null, status: 'retired' },
  { id: 'dsh', display_name: 'DSH', role: 'principal', model: null, status: 'registered' },
  { id: 'commandcode', display_name: 'Command Code', role: 'external', model: null, status: 'registered' },
  // Sentinel: no real gateway can contain this name, so if it renders the
  // roster provably came from this spec rather than a developer's live room.
  { id: 'smoke-sentinel', display_name: 'Smoke Sentinel', role: 'external', model: null, status: 'registered' },
];

const ROOM = {
  id: 'workspace_global',
  name: 'Global Agent Room',
  objective: 'Shared durable coordination.',
  status: 'active',
  created_at: 1,
  updated_at: 1,
  agents: ROSTER,
  messages: [],
  events: [],
  turns: [],
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });

  // Playwright gives the MOST RECENTLY registered matching route precedence,
  // so the refuse-by-default catch-all goes FIRST and every real stub is
  // registered after it. Without this, an endpoint this spec forgets is
  // silently proxied to whatever gateway is live on the machine — which in an
  // earlier run leaked real room traffic into the transcript under test.
  await page.route('**/proxy/**', (route) => {
    if (route.request().method() !== 'GET') return route.fulfill({ json: {} });
    return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'unstubbed in smoke' }) });
  });

  // HealthGate blocks rendering until /proxy/health answers 200; everything
  // below must therefore be registered after the catch-all.
  await page.route('**/proxy/health', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) }),
  );
  await page.route('**/proxy/onboarding', route => route.fulfill({ json: { onboarded: true } }));
  await page.route('**/proxy/api/models', route =>
    route.fulfill({ json: { data: [{ id: 'kitty-default' }] } }),
  );
  await page.route('**/proxy/models/picker', route =>
    route.fulfill({
      json: {
        schema_version: 1, source: 'smoke-roster',
        discovery: { state: 'available', reason: null, checked_at: null },
        claims: { role_tags: 'heuristic', alternatives: 'cost-screened only' },
        presets: [{
          role: 'auto', label: 'Daily Kitty', route: 'kitty-default', purpose: 'Everyday use.',
          kind: 'router', provider: null, model: null, configured: true, catalogue: null,
          catalogue_state: 'not_applicable', alternatives: [],
        }],
      },
    }),
  );
  await page.route('**/proxy/runtime/**', route =>
    route.fulfill({
      json: {
        revision: 'smoke-roster',
        connections: { gateway: { state: 'available', reason: null } },
        inference: { available_models: { state: 'available', value: ['kitty-default'] } },
        tools: { state: 'available' }, context: { active_project: { value: null } },
        execution: { builder: { value: null, state: 'available' } },
      },
    }),
  );
  await page.route('**/proxy/activity**', route =>
    route.fulfill({ json: { counts: {}, sources: {} } }),
  );

  // One dispatcher for the whole room subtree. Separate `/inbox*`-style
  // patterns are not enough: `*` does not cross `/`, so `/inbox/jacob?...`
  // would fall through to the catch-all.
  await page.route('**/proxy/agent-room/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/messages') || path.includes('/inbox') || path.includes('/threads/')) {
      return route.fulfill({ json: { messages: [] } });
    }
    return route.fulfill({ json: ROOM });
  });
});

test('Agent Room lists every live participant by display name, including ones added later', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'mobile', 'Agents lives in the mobile More overflow');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });

  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await nav.getByRole('button', { name: 'More', exact: true }).click();
  const menu = page.getByRole('menu', { name: 'More destinations' });
  await expect(menu).toBeVisible();
  await menu.getByRole('menuitem', { name: 'Agents', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Global Agent Room', exact: true })).toBeVisible({ timeout: 15_000 });

  // The roster section (the Card exposes an aria-label but no landmark role, so
  // it is targeted by that attribute).
  const roster = page.locator('div[aria-label="Registered agents"]');
  await expect(roster).toBeVisible();

  // Proves the list is response-derived: none of these names existed in the old
  // hardcoded copy of the roster.
  await expect(roster.getByText('Smoke Sentinel', { exact: true })).toBeVisible();
  await expect(roster.getByText('DSH', { exact: true })).toBeVisible();
  await expect(roster.getByText('Command Code', { exact: true })).toBeVisible();

  // Statuses come from the response instead of a blanket "registered" label.
  await expect(roster.getByText('retired', { exact: true })).toHaveCount(1);
  await expect(roster.getByText('registered', { exact: true })).toHaveCount(4);

  // A known participant must not fall back to its raw id.
  await expect(roster.getByText('commandcode', { exact: true })).toHaveCount(0);

  await expect(page.getByRole('heading', { name: 'Room transcript', exact: true })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `horizontal overflow ${overflow}px`).toBeLessThanOrEqual(0);

  expect(errors, `page errors: ${errors.join(' | ')}`).toEqual([]);
});
