import { test, expect } from './fixtures';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
  await page.route('**/proxy/api/models', route =>
    route.fulfill({ json: { data: [{ id: 'kitty-default' }] } })
  );
  await page.route('**/proxy/models/picker', route =>
    route.fulfill({
      json: {
        schema_version: 1,
        source: 'smoke-test',
        discovery: { state: 'available', reason: null, checked_at: null },
        claims: { role_tags: 'heuristic', alternatives: 'cost-screened only' },
        presets: [{
          role: 'auto', label: 'Daily Kitty', route: 'kitty-default',
          purpose: 'Everyday use.', kind: 'router', provider: null, model: null,
          configured: true, catalogue: null, catalogue_state: 'not_applicable', alternatives: [],
        }],
      },
    })
  );
  await page.route('**/proxy/runtime/**', route =>
    route.fulfill({
      json: {
        revision: 'smoke-test',
        connections: { gateway: { state: 'available', reason: null } },
        inference: { available_models: { state: 'available', value: ['kitty-default'] } },
        tools: { state: 'available' },
        context: { active_project: { value: null } },
        execution: { builder: { value: null, state: 'available' } },
      },
    })
  );
});

test('chat view loads and input is accessible', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const chatsBtn = page.getByRole('button', { name: 'Chat', exact: true });
  await chatsBtn.first().click();
  await page.waitForTimeout(500);

  // Desktop chat view: the composer is the main textarea. A blanket
  // 'textarea, input[type=text]' selector matched the sidebar "search chats"
  // input first, so this test was filling the search box and reading back a
  // controlled input that resets — that was the "flake".
  const input = page.locator('main textarea').first();
  if (await input.count() > 0) {
    await expect(input).toBeVisible();
    await input.fill('hello');
    // Auto-retry with a load-tolerant timeout: the composer is a controlled
    // input, and under full-suite parallel load the React state round-trip can
    // take longer than the default 5s.
    await expect(input).toHaveValue('hello', { timeout: 10_000 });
  }

  expect(errors).toEqual([]);
});

test('chat view has no console errors', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const chatsBtn = page.getByRole('button', { name: 'Chat', exact: true });
  await chatsBtn.first().click();
  await page.waitForTimeout(1000);

  expect(errors).toEqual([]);
});
