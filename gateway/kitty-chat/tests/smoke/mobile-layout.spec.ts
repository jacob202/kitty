import { test, expect } from './fixtures';

/** Phone-layout regressions Jacob hit on an iPhone: content scrolling sideways,
 *  the composer buried under the tab bar, and the chat drawer rendering
 *  see-through. These assert geometry, not markup, so they catch the class of
 *  bug rather than one instance of it. */

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

test.describe('phone layout', () => {
  test.beforeEach(({ }, testInfo) => {
    testInfo.skip(testInfo.project.name !== 'mobile', 'phone-only geometry');
  });

  test('nothing overflows the viewport horizontally', async ({ page }) => {
    // A live gateway fills the header with a project name and real model ids —
    // the state Jacob actually runs in, and the one that overflowed.
    await page.route('**/proxy/projects', (route) =>
      route.fulfill({ json: { projects: [{ id: 1, name: 'kitty-gateway-rebuild' }] } })
    );
    await page.route('**/proxy/api/models', (route) =>
      route.fulfill({
        json: { data: [{ id: 'kitty-default' }, { id: 'kitty-sonnet' }, { id: 'kitty-small' }] },
      })
    );

    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

    const overflow = await page.evaluate(() => {
      const width = document.documentElement.clientWidth;
      const offenders: Array<{ tag: string; label: string; right: number }> = [];
      for (const el of Array.from(document.querySelectorAll('body *'))) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        // Only report the outermost offender in a chain, not every descendant.
        if (rect.right > width + 1 && !offenders.some((o) => el.closest(o.tag) !== null)) {
          offenders.push({
            tag: el.tagName.toLowerCase(),
            label: (el.getAttribute('aria-label') ?? el.textContent ?? '').slice(0, 40),
            right: Math.round(rect.right),
          });
        }
      }
      return { width, scrollWidth: document.documentElement.scrollWidth, offenders };
    });

    expect(overflow.offenders, JSON.stringify(overflow.offenders, null, 2)).toEqual([]);
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.width + 1);
  });

  test('the tab bar does not cover the chat composer', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    await expect(nav).toBeVisible();
    await nav.getByRole('button', { name: 'Chat', exact: true }).click();

    const composer = page.locator('textarea').first();
    await expect(composer).toBeVisible();

    const navBox = await nav.boundingBox();
    const composerBox = await composer.boundingBox();
    expect(navBox).not.toBeNull();
    expect(composerBox).not.toBeNull();

    const composerBottom = composerBox!.y + composerBox!.height;
    expect(
      composerBottom,
      `composer ends at ${composerBottom}, tab bar starts at ${navBox!.y}`,
    ).toBeLessThanOrEqual(navBox!.y + 1);
  });

  test('every tab-bar item is fully on screen', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

    const width = await page.evaluate(() => document.documentElement.clientWidth);
    const buttons = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const button = buttons.nth(i);
      const label = await button.getAttribute('aria-label');
      const box = await button.boundingBox();
      expect(box, `${label} has no box`).not.toBeNull();
      expect(box!.x, `${label} starts off-screen`).toBeGreaterThanOrEqual(-1);
      expect(box!.x + box!.width, `${label} ends off-screen`).toBeLessThanOrEqual(width + 1);
    }
  });

  test('the chat drawer is opaque, not see-through', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    await nav.getByRole('button', { name: 'Chat', exact: true }).click();
    await page.getByRole('button', { name: 'Open sidebar' }).click();
    const drawer = page.getByTestId('mobile-chat-drawer');
    await expect(drawer).toBeVisible();

    const alpha = await drawer.evaluate((el) => {
      const bg = getComputedStyle(el).backgroundColor;
      const match = bg.match(/rgba?\(([^)]+)\)/);
      if (!match) return 1;
      const parts = match[1].split(',').map((p) => parseFloat(p.trim()));
      return parts.length > 3 ? parts[3] : 1;
    });

    expect(alpha, 'drawer background must be fully opaque over page content').toBe(1);
  });
});

test('phone chat composer uses readable text and touch-sized controls', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'mobile', 'phone-only composer contract');

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await nav.getByRole('button', { name: 'Chat', exact: true }).click();

  const composer = page.locator('main textarea').first();
  await expect(composer).toBeVisible();
  expect(await composer.evaluate((el) => getComputedStyle(el).fontSize)).toBe('16px');

  for (const label of ['attach a file', 'start voice input']) {
    const control = page.getByRole('button', { name: label });
    const box = await control.boundingBox();
    expect(box, `${label} has no box`).not.toBeNull();
    expect(box!.width, `${label} is too narrow`).toBeGreaterThanOrEqual(44);
    expect(box!.height, `${label} is too short`).toBeGreaterThanOrEqual(44);
  }
});
