import { test, expect } from './fixtures';
import type { Page } from '@playwright/test';

/**
 * Slice 1 phone dogfood gate (#346 Slice 1). This is not a component/unit-test
 * substitute: it drives the real running app at an iPhone 14 Pro-class viewport
 * through every primary destination and fails on the exact defects Jacob hit on
 * his phone — horizontal overflow, clipped controls, actions hidden under the
 * fixed tab bar, missing bottom-nav items, a Studio that invites an impossible
 * generation, and a Library that demands a Mac file path.
 *
 * Runs without a live gateway: the health stub mounts the app and every other
 * endpoint degrades to 503 in CI. Long project/model names and an unbreakable
 * source basename are stubbed in because those are the values that overflowed.
 */

const DESTINATIONS = ['Home', 'Chat', 'Work', 'Studio', 'Library', 'More'];

const GATEWAY_STUBS = [
  ['**/proxy/projects', { projects: [{ id: 1, name: 'kitty-gateway-rebuild' }] }],
  ['**/proxy/api/models', { data: [{ id: 'deepseek-v4-pro' }, { id: 'kitty-sonnet' }, { id: 'deepseek-v4-flash' }] }],
  ['**/proxy/image/status', {
    available: false,
    backend: 'comfyui',
    engines: [
      { name: 'comfyui', label: 'ComfyUI', available: false },
      { name: 'drawthings', label: 'Draw Things', available: false },
    ],
  }],
  ['**/proxy/knowledge/sources', {
    total_sources: 2,
    total_chunks: 3,
    sources: [
      {
        name: 'MPEG.7.Audio.and.Beyond.Audio.Content.Indexing.and.Retrieval',
        collection: 'expert_builder',
        tags: ['technical'],
        chunks: 3,
      },
    ],
  }],
] as const;

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

async function stubGateway(page: Page) {
  for (const [url, json] of GATEWAY_STUBS) {
    await page.route(url, (route) => route.fulfill({ json }));
  }
  // Any generation/planning attempt must fail loudly so the test can prove it
  // is never dispatched while engines are offline.
  await page.route('**/proxy/studio/generate', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'ComfyUI is not running' }),
  }));
  await page.route('**/proxy/studio/plan', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'ComfyUI is not running' }),
  }));
}

async function collectOverflow(page: Page) {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const offenders: Array<{ tag: string; right: number; width: number; text: string }> = [];
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.right > width + 1) {
        offenders.push({
          tag: el.tagName.toLowerCase(),
          right: Math.round(r.right),
          width: Math.round(r.width),
          text: (el.textContent ?? '').slice(0, 40).replace(/\s+/g, ' '),
        });
      }
    }
    return { width, scrollWidth: document.documentElement.scrollWidth, offenders: offenders.slice(0, 8) };
  });
}

async function scrollMainToBottom(page: Page) {
  // Scroll every scrollable inside main to its bottom and keep re-scrolling
  // until nothing moves — heavy views (Settings) grow as queries resolve, and a
  // single pass can land before that growth, leaving the last control below the
  // fold right at measure time.
  await page.evaluate(async () => {
    const scrollers = () =>
      Array.from(document.querySelectorAll('main *'))
        .filter((el) => {
          const cs = getComputedStyle(el);
          return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 2;
        })
        .filter((el) => !(el as HTMLElement).closest('[aria-label="Main navigation"]'));
    for (let i = 0; i < 6; i++) {
      const list = scrollers();
      if (list.length === 0) break;
      let moved = false;
      for (const s of list) {
        const t = s.scrollTop;
        s.scrollTop = s.scrollHeight;
        if (s.scrollTop !== t) moved = true;
      }
      await new Promise((r) => setTimeout(r, 250));
      if (!moved) break;
    }
  });
  await page.waitForTimeout(200);
}

async function lowestInteractiveAboveNav(page: Page, navTop: number) {
  return page.evaluate((navY) => {
    const interactive = 'button, input, textarea, select, a[href], [role="button"], [role="link"], [role="tab"], [contenteditable="true"]';
    let worst: { bottom: number; label: string } | null = null;
    for (const el of Array.from(document.querySelectorAll(interactive))) {
      // Skip the fixed tab bar itself and anything inside it.
      const fixed = el.closest('nav[aria-label="Main navigation"]');
      const inNav = el.closest('[aria-label="Main navigation"]') !== null;
      if (fixed || inNav) continue;
      const style = getComputedStyle(el);
      if (style.position === 'fixed' || style.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.bottom > (worst?.bottom ?? -1)) {
        worst = {
          bottom: r.bottom,
          label: (el.getAttribute('aria-label') ?? el.textContent ?? '').slice(0, 40),
        };
      }
    }
    return { ok: worst === null || worst.bottom <= navY + 1, detail: worst ? `${worst.label} bottom=${Math.round(worst.bottom)} vs nav top=${Math.round(navY)}` : 'no interactive element' };
  }, navTop);
}

/** Scroll to the bottom and verify the last actionable clear the fixed tab bar.
 *  Retries because heavy views keep growing as late queries resolve, pushing a
 *  control back below the fold right at measure time. */
async function assertLastActionableClearsNav(page: Page, navTop: number, label: string) {
  let last: { ok: boolean; detail: string } | null = null;
  for (let attempt = 0; attempt < 6; attempt++) {
    await scrollMainToBottom(page);
    last = await lowestInteractiveAboveNav(page, navTop);
    if (last.ok) break;
    await page.waitForTimeout(500);
  }
  expect(last!.ok, `[${label}] ${last!.detail}`).toBe(true);
}

test.describe('phone dogfood — slice 1', () => {
  test.beforeEach(({}, testInfo) => {
    testInfo.skip(testInfo.project.name !== 'mobile', 'phone-only acceptance');
  });

  test.beforeEach(async ({ page }) => {
    await stubGateway(page);
  });

  test('all six destinations: no overflow, full nav, reachable actions above the tab bar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });

    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    const navBox = await nav.boundingBox();
    expect(navBox, 'tab bar has a box').not.toBeNull();

    for (const label of DESTINATIONS) {
      await nav.getByRole('button', { name: label, exact: true }).click();
      await expect(page.locator('main')).toBeVisible();
      // Async content (sources list, model chips, usage) can land after the view
      // mounts; a single early measurement would miss overflow that appears once
      // the data renders. Take a second reading and fail on any offender from
      // either.
      await page.waitForTimeout(800);
      const firstRead = await collectOverflow(page);
      await page.waitForTimeout(700);
      const secondRead = await collectOverflow(page);

      const seen = new Set<string>();
      const offenders = [...firstRead.offenders, ...secondRead.offenders]
        .filter((o) => {
          const key = `${o.tag}:${o.right}`;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        })
        .slice(0, 8);
      const scrollWidth = Math.max(firstRead.scrollWidth, secondRead.scrollWidth);
      const width = firstRead.width;

      // 1) no document-level horizontal scroll and no element overhangs the right edge.
      expect(scrollWidth, `[${label}] page scrollWidth ${scrollWidth} > viewport ${width}`).toBeLessThanOrEqual(width + 1);
      expect(offenders, `[${label}] elements overhang the right edge:\n${JSON.stringify(offenders, null, 2)}`).toEqual([]);

      // 2) all six bottom-nav items are present and fully on screen.
      const buttons = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button');
      expect(await buttons.count(), `[${label}] should render six bottom-nav items`).toBe(6);
      for (let i = 0; i < 6; i++) {
        const box = await buttons.nth(i).boundingBox();
        expect(box, `[${label}] nav item ${i} has a box`).not.toBeNull();
        expect(box!.x, `[${label}] nav item ${i} starts off-screen`).toBeGreaterThanOrEqual(-1);
        expect(box!.x + box!.width, `[${label}] nav item ${i} ends off-screen`).toBeLessThanOrEqual(width + 1);
      }

      // 3) after scrolling to the bottom, the last actionable control clears the tab bar.
      await scrollMainToBottom(page);
      await assertLastActionableClearsNav(page, navBox!.y, label);
    }
  });

  test('Studio/More tab bar does not bury the last control behind the fixed nav', async ({ page }) => {
    // Covered by the destination sweep, but pin the two destinations that had
    // real clipping (Settings' long rows) with an explicit assertion.
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    const navBox = await nav.boundingBox();
    expect(navBox).not.toBeNull();

    for (const label of ['Studio', 'More']) {
      await nav.getByRole('button', { name: label, exact: true }).click();
      await page.waitForTimeout(900);
      await scrollMainToBottom(page);
      await assertLastActionableClearsNav(page, navBox!.y, label);
    }
  });

  test('Studio fails closed with no image engine and never dispatches generation', async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem('kitty-onboarded', 'true'));
    await stubGateway(page);

    let generationAttempts = 0;
    await page.route('**/proxy/studio/generate', (route) => { generationAttempts += 1; route.fulfill({ status: 503, body: '{}' }); });

    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Studio' }).click();
    await page.waitForTimeout(400);

    await expect(page.getByTestId('studio-offline')).toBeVisible();
    await expect(page.getByTestId('studio-check-again')).toBeVisible();

    // Renderer-independent work stays available (finding 3): the editor is
    // visible; with a prompt entered, plan preview is enabled — but generation
    // stays disabled because no renderer is available.
    await page.locator('main').getByPlaceholder(/describe what you want to create/i).fill('a sleeping cat');
    await expect(page.locator('main').getByRole('button', { name: 'preview plan', exact: true })).toBeEnabled();
    const generate = page.locator('main').getByRole('button', { name: 'generate', exact: true });
    await expect(generate).toBeDisabled();
    await expect(page.locator('main').getByPlaceholder(/describe what you want to create/i)).toBeVisible();

    // No raw Internal Server Error; only the human offline message.
    await expect(page.locator('main').getByText('Internal Server Error')).toHaveCount(0);
    await expect(page.getByTestId('studio-offline')).toContainText('Plan preview and characters still work');

    // The recovery action actually re-checks (and stays fail-closed).
    await page.getByTestId('studio-check-again').click();
    await expect(page.getByTestId('studio-check-again')).toBeVisible();

    expect(generationAttempts, 'no generation request may be dispatched while engines are offline').toBe(0);
  });

  test('Studio character dialog stays fully inside the viewport when engines are available', async ({ page }) => {
    await stubEnginesOnline(page);
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Studio' }).click();
    await page.waitForTimeout(400);

    // Open the character picker, then the create-character dialog.
    await page.locator('main').getByRole('button', { name: /character/i }).first().click();
    await page.locator('main').getByRole('button', { name: 'new character' }).click();
    const dialog = page.getByRole('dialog', { name: 'create character' });
    await expect(dialog).toBeVisible();
    // The role=dialog node is the full-viewport overlay; measure the inner card,
    // which is what must actually fit — no horizontal clipping, every action on screen.
    const card = dialog.locator(':scope > div');
    const vw = await page.evaluate(() => window.innerWidth);
    const vh = await page.evaluate(() => window.innerHeight);
    const box = await card.boundingBox();
    expect(box, 'character dialog card has a box').not.toBeNull();
    expect(box!.x, 'character dialog starts off-screen left').toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width, 'character dialog overflows right edge').toBeLessThanOrEqual(vw + 1);
    expect(box!.y, 'character dialog starts off-screen top').toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height, 'character dialog overflows viewport bottom').toBeLessThanOrEqual(vh + 1);

    const cancelBtn = dialog.getByRole('button', { name: 'cancel' });
    expect(await cancelBtn.isVisible(), 'cancel stays visible/tappable in the character dialog').toBe(true);
  });

  test('Library on mobile uses the native file picker and hides the Mac-path control', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Library' }).click();
    await page.waitForTimeout(400);

    await expect(page.getByTestId('library-file-picker')).toBeVisible();
    await expect(page.getByTestId('library-path-control')).toHaveCount(0);
    await expect(page.locator('main').getByText(/file path on the Mac/i)).toHaveCount(0);

    // The native file input still exists behind the picker.
    const fileInput = page.locator('input[type="file"][accept*=".pdf"]');
    expect(await fileInput.count(), 'native file input present').toBeGreaterThanOrEqual(1);
  });
});

async function stubEnginesOnline(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem('kitty-onboarded', 'true'));
  for (const [url, json] of GATEWAY_STUBS) {
    await page.route(url, (route) => route.fulfill({
      json: url === '**/proxy/image/status'
        ? {
          available: true,
          backend: 'comfyui',
          engines: [{ name: 'comfyui', label: 'ComfyUI', available: true }],
        }
        : json,
    }));
  }
}
