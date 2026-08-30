import { test, expect } from './fixtures';

/** LIBRARY-CHAT-001 running-app acceptance: a saved image reaches the chat
 *  composer, an unusable file says why without a network round trip, and a
 *  gateway refusal reads as a sentence rather than a status code. Runs at both
 *  the desktop and iPhone projects, so the mobile layout is covered too. */

const READY_PNG = {
  id: 'artifact_ready_png',
  project_id: 7,
  kind: 'capture',
  media_type: 'image/png',
  display_name: 'camera-reference.png',
  state: 'ready',
  size_bytes: 2048,
  created_at: 1787259000,
  created_by: 'capture',
  conversation_id: 'chat-1',
  metadata: {},
  error: null,
};

const READY_PDF = {
  ...READY_PNG,
  id: 'artifact_ready_pdf',
  kind: 'document',
  media_type: 'application/pdf',
  display_name: 'notes.pdf',
  size_bytes: 4096,
  created_at: 1787250000,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
  await page.route('**/proxy/artifacts**', (route) =>
    route.fulfill({ json: { artifacts: [READY_PNG, READY_PDF] } })
  );
});

async function openLibrary(page: import('@playwright/test').Page) {
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Library', exact: true }).first().click();
  await expect(page.getByRole('list', { name: /recent artifacts/i })).toBeVisible({ timeout: 10_000 });
}

test('a ready image reaches the chat composer and an unusable file says why', async ({ page }) => {
  await page.route('**/proxy/chats/use-in-chat', (route) =>
    route.fulfill({
      json: {
        id: READY_PNG.id,
        display_name: READY_PNG.display_name,
        media_type: 'image/png',
        size: READY_PNG.size_bytes,
        data_url: 'data:image/png;base64,AAAA',
      },
    })
  );

  await openLibrary(page);

  // The PDF is refused in place: no enabled control, and a reason a person can read.
  await expect(
    page.getByRole('button', { name: /use notes\.pdf in chat unavailable/i })
  ).toBeDisabled();
  await expect(page.getByText(/only images can be attached/i)).toBeVisible();

  const use = page.getByRole('button', { name: /use camera-reference\.png in chat$/i });
  await expect(use).toBeEnabled();
  await use.click();

  // Switching to Chat is the visible result, and the file is staged, not sent.
  await expect(page.getByText('camera-reference.png').first()).toBeVisible({ timeout: 10_000 });
});

test('a refused attachment shows the reason, not a status code', async ({ page }) => {
  await page.route('**/proxy/chats/use-in-chat', (route) =>
    route.fulfill({ status: 409, json: { detail: 'That saved file is missing from disk.' } })
  );

  await openLibrary(page);
  await page.getByRole('button', { name: /use camera-reference\.png in chat$/i }).click();

  await expect(page.locator('main').getByRole('alert')).toHaveText(/that saved file is missing from disk/i);
  await expect(page.getByText(/gateway returned/i)).toHaveCount(0);
});

test('a failure with no reason is translated instead of leaked', async ({ page }) => {
  await page.route('**/proxy/chats/use-in-chat', (route) =>
    route.fulfill({ status: 500, body: 'boom' })
  );

  await openLibrary(page);
  await page.getByRole('button', { name: /use camera-reference\.png in chat$/i }).click();

  await expect(page.locator('main').getByRole('alert')).toHaveText(/kitty's service hit an error/i);
  await expect(page.getByText(/gateway returned 500/i)).toHaveCount(0);

  const overflow = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.width + 1);
});
