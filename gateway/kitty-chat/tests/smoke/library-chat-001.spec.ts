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

test('failed image send retries once with the same attachment and reload restores it', async ({ page }) => {
  const sentBodies: Array<Record<string, unknown>> = [];
  let persistedChats: Array<Record<string, unknown>> = [];
  const persistedLifecycle: Record<string, Array<Record<string, unknown>>> = {};

  // Sending is intentionally disabled when model availability is unknown.
  // Give this frontend-only smoke a truthful available-model contract so the
  // composer exercises the real send/retry path without contacting a provider.
  await page.route('**/proxy/api/models', (route) =>
    route.fulfill({ json: { data: [{ id: 'kitty-default' }] } })
  );
  await page.route('**/proxy/models/picker', (route) =>
    route.fulfill({
      json: {
        schema_version: 1,
        source: 'library-chat-smoke',
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
  await page.route('**/proxy/runtime/**', (route) =>
    route.fulfill({
      json: {
        revision: 'library-chat-smoke',
        connections: { gateway: { state: 'available', reason: null } },
        inference: { available_models: { state: 'available', value: ['kitty-default'] } },
        tools: { state: 'available' },
        context: { active_project: { value: null } },
        execution: { builder: { value: null, state: 'available' } },
      },
    })
  );

  await page.route('**/proxy/chats/use-in-chat', (route) =>
    route.fulfill({
      json: {
        id: READY_PNG.id,
        display_name: READY_PNG.display_name,
        media_type: READY_PNG.media_type,
        size: READY_PNG.size_bytes,
      },
    })
  );

  await page.route('**/proxy/chats/*/messages', (route) => {
    const url = new URL(route.request().url());
    const parts = url.pathname.split('/');
    const chatId = decodeURIComponent(parts[parts.length - 2] ?? '');
    return route.fulfill({
      json: {
        conversation_id: chatId,
        messages: persistedLifecycle[chatId] ?? [],
      },
    });
  });

  await page.route('**/proxy/chats', (route) => {
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      if (typeof body.id === 'string') {
        persistedChats = persistedChats.filter((chat) => chat.id !== body.id);
        persistedChats.push(body);
      }
      return route.fulfill({ json: { ok: true } });
    }
    return route.fulfill({ json: { chats: persistedChats } });
  });

  await page.route('**/proxy/api/chat/completions', (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    sentBodies.push(body);

    if (sentBodies.length === 1) {
      return route.fulfill({
        status: 503,
        json: { detail: 'provider unavailable' },
      });
    }

    const chatId = String(body.conversation_id);
    const now = Math.floor(Date.now() / 1000);
    const rawMessages = Array.isArray(body.messages) ? body.messages : [];
    const latestUser = [...rawMessages].reverse().find(
      (message): message is { role: string; content: string } =>
        typeof message === 'object' && message !== null &&
        (message as { role?: unknown }).role === 'user' &&
        typeof (message as { content?: unknown }).content === 'string'
    );

    persistedChats = [{
      id: chatId,
      title: String(body.conversation_title ?? 'image chat'),
      model: String(body.model ?? 'kitty-default'),
      color: 'teal',
      createdAt: new Date(now * 1000).toISOString(),
      updatedAt: new Date(now * 1000).toISOString(),
      messages: [],
    }];
    persistedLifecycle[chatId] = [
      {
        id: String(body.user_message_id),
        role: 'user',
        content: latestUser?.content ?? '',
        created_at: now,
        status: 'succeeded',
        attachments: [{
          id: READY_PNG.id,
          display_name: READY_PNG.display_name,
          media_type: READY_PNG.media_type,
          size: READY_PNG.size_bytes,
        }],
      },
      {
        id: 'assistant-image-retry',
        role: 'assistant',
        content: 'I can see the image.',
        created_at: now + 1,
        model: 'kitty-default',
        status: 'succeeded',
        attachments: [],
      },
    ];

    return route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: 'data: {"choices":[{"delta":{"content":"I can see the image."}}]}\n\ndata: [DONE]\n\n',
    });
  });

  await openLibrary(page);
  await page.getByRole('button', { name: /use camera-reference\.png in chat$/i }).click();

  const composer = page.locator('textarea').first();
  await expect(composer).toBeVisible({ timeout: 10_000 });
  await composer.fill('what do you see?');
  await page.getByRole('button', { name: /send message/i }).click();

  await expect(page.locator('.msg-in').filter({ hasText: /model provider couldn't finish/i }).first())
    .toBeVisible({ timeout: 10_000 });
  expect(sentBodies).toHaveLength(1);
  expect(sentBodies[0].attachment_ids).toEqual([READY_PNG.id]);
  expect(sentBodies[0].image_attachment_ids).toEqual([READY_PNG.id]);

  await page.getByRole('button', { name: /retry message/i }).click();
  await expect(page.locator('.msg-in').filter({ hasText: /I can see the image\./i }).first())
    .toBeVisible({ timeout: 10_000 });

  expect(sentBodies).toHaveLength(2);
  expect(sentBodies[1].attachment_ids).toEqual([READY_PNG.id]);
  expect(sentBodies[1].image_attachment_ids).toEqual([READY_PNG.id]);

  await page.reload();
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
  const chatButton = page.getByRole('button', { name: /^chat$/i }).first();
  if (await chatButton.isVisible()) await chatButton.click();

  await expect(page.getByText(READY_PNG.display_name).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('.msg-in').filter({ hasText: /I can see the image\./i }).first())
    .toBeVisible({ timeout: 10_000 });

  const overflow = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.width + 1);
});
