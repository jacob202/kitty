import { test, expect } from './fixtures';

test('probe page API surface', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
  const methods = [
    'getByLabelText', 'getByRole', 'getByText', 'getByTestId',
    'locator', 'goto', 'route', 'addInitScript',
  ];
  const missing = methods.filter((m) => typeof (page as unknown as Record<string, unknown>)[m] !== 'function');
  console.log('MISSING METHODS:', JSON.stringify(missing));
  expect(missing).toEqual([]);
});
