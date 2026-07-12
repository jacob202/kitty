import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Pre-dismiss onboarding modal
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

test('page loads without console errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page).toHaveTitle(/Kitty/i);

  const body = page.locator('main');
  await expect(body).toBeVisible({ timeout: 10_000 });
  expect(errors).toEqual([]);
});

test('page has visible content', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });
  const text = await page.locator('body').innerText();
  expect(text.length).toBeGreaterThan(0);
});
