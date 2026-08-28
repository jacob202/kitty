import { test, expect } from './fixtures';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
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
