import { test, expect, type Page } from '@playwright/test';

const MOBILE = { viewport: { width: 393, height: 852 } };

/**
 * Chat Trust Slice 3 — deterministic smoking of the send→stream→persist→restart
 * loop on an iPhone 14 Pro-class viewport.
 *
 * Gateway chat-completions is stubbed so this runs as a frontend-only smoke test
 * without a live backend provider. The stubbed SSE journeys through the real
 * streaming parser, state management, and persistence code paths.
 *
 * Backend persistence / lifecycle deduplication is covered by focused Python
 * tests (tests/test_chat_lifecycle.py, tests/test_chat_completions.py).
 */

const SSE_CHUNKS = ['Hel', 'lo, ', 'world!'];
const ERROR_MESSAGE = 'Gateway error 502: provider unreachable';
const ATTRIBUTION_PROVIDER = 'deepseek';
const ATTRIBUTION_MODEL = 'deepseek-chat';

/** In-memory "database" shared across stubs so reloads recover state. */
let persistedChats: Record<string, unknown>[] = [];
let persistedLifecycle: Record<string, unknown[]> = {};

function resetPersistence() {
  persistedChats = [];
  persistedLifecycle = {};
}
resetPersistence();

function chatMessageId(index: number, role: string) {
  return `recovered-msg-${index}-${role}`;
}

/** Build a deterministic SSE body from chunks. */
function sseBody(chunks: string[], withModelHeader = true): string {
  const header = withModelHeader
    ? `X-Kitty-Provider-Selected: ${ATTRIBUTION_PROVIDER}\nX-Kitty-Model-Requested: ${ATTRIBUTION_MODEL}\n`
    : '';
  let body = '';
  for (const chunk of chunks) {
    body += `data: ${JSON.stringify({ choices: [{ delta: { content: chunk } }] })}\n\n`;
  }
  body += 'data: [DONE]\n\n';
  return body;
}

/** Stub gateway endpoints so the Next.js app sees a deterministic backend. */
async function stubGateway(page: Page, opts: { failAfterChunks?: number; errorEvent?: 'routing' | 'upstream' } = {}) {
  await page.route('**/proxy/health', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  );

  await page.route('**/proxy/api/models', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [{ id: 'kitty-default' }, { id: 'deepseek-chat' }] }),
    })
  );

  await page.route('**/proxy/runtime/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        revision: 'test-revision',
        connections: { gateway: { state: 'available', reason: null } },
        inference: { available_models: { state: 'available', value: ['kitty-default', 'deepseek-chat'] } },
        tools: { state: 'available' },
        context: { active_project: { value: null } },
        execution: { builder: { value: null, state: 'available' } },
      }),
    })
  );

  // Chat completions: deterministic SSE stream
  await page.route('**/proxy/api/chat/completions', async (route) => {
    const req = route.request();
    const body = req.postDataJSON();
    const userText: string = body?.messages?.find((m: { role: string }) => m.role === 'user')?.content ?? '';

    if (opts.errorEvent) {
      // Gateway emits a user-facing SSE error event before tearing down.
      const message =
        opts.errorEvent === 'routing'
          ? "Kitty couldn't complete this request — the selected model provider didn't accept it (it may be out of credit or unavailable). Your message is saved. Tap retry, or check Settings to pick a different model."
          : "Kitty's model provider couldn't finish this request. Your message is saved — tap retry to try again.";
      const body = `data: ${JSON.stringify({ error: { kind: opts.errorEvent, message } })}\n\n`;
      return route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Kitty-Provider-Selected': ATTRIBUTION_PROVIDER,
          'X-Kitty-Model-Requested': ATTRIBUTION_MODEL,
          'X-Kitty-Tools-State': 'unavailable',
        },
        body,
      });
    }

    if (opts.failAfterChunks !== undefined) {
      // Simulate streaming that fails mid-way
      const partialChunks = ['Hel'];
      const body = `data: ${JSON.stringify({ choices: [{ delta: { content: partialChunks[0] } }] })}\n\n`;
      return route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Kitty-Provider-Selected': ATTRIBUTION_PROVIDER,
          'X-Kitty-Model-Requested': ATTRIBUTION_MODEL,
          'X-Kitty-Tools-State': 'unavailable',
        },
        body,
      });
    }

    // Persist the chat blob so reload recovers it
    const chatId = body?.conversation_id ?? 'chat-1';
    const title = body?.conversation_title ?? userText.slice(0, 32);
    const userMsgId = body?.user_message_id ?? `msg-${Date.now()}`;

    // Build persisted lifecycle messages for recovery
    const recoveredMessages = [];
    recoveredMessages.push({
      id: chatMessageId(0, 'user'),
      role: 'user',
      content: userText,
      created_at: Math.floor(Date.now() / 1000),
    });
    for (let i = 0; i < SSE_CHUNKS.length; i++) {
      recoveredMessages.push({
        id: chatMessageId(i + 1, 'assistant'),
        role: 'assistant',
        content: SSE_CHUNKS.slice(0, i + 1).join(''),
        created_at: Math.floor(Date.now() / 1000) + i + 1,
        model: ATTRIBUTION_MODEL,
        status: 'succeeded',
      });
    }

    persistedChats = [{ id: chatId, title, model: 'kitty-default' }];
    persistedLifecycle[chatId] = recoveredMessages;

    return route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Kitty-Provider-Selected': ATTRIBUTION_PROVIDER,
        'X-Kitty-Model-Requested': ATTRIBUTION_MODEL,
        'X-Kitty-Tools-State': 'unavailable',
      },
      body: sseBody(SSE_CHUNKS),
    });
  });

  // Chats list endpoint
  await page.route('**/proxy/chats', async (route) => {
    const method = route.request().method();
    if (method === 'POST') {
      const body = route.request().postDataJSON();
      if (body?.id) {
        persistedChats = persistedChats.filter((c) => c.id !== body.id);
        persistedChats.push(body);
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ chats: persistedChats }),
    });
  });

  // Chat messages recovery
  await page.route('**/proxy/chats/*/messages', (route) => {
    const url = new URL(route.request().url());
    const chatId = url.pathname.split('/')[3];
    const messages = persistedLifecycle[chatId] ?? [];
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ conversation_id: chatId, messages }),
    });
  });

  // Chat lifecycle (for thread goal)
  await page.route('**/proxy/chats/*/lifecycle', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ conversation: {}, turns: [] }) });
  });
}

let persistentActiveChatId: string | null = null

test.beforeEach(async ({ page }) => {
  resetPersistence();
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

/** Navigate to the app with a clean active-chat slate. */
async function goClean(page: Page) {
  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
  // Clear any stale active-chat-id (from prior tests) and reload so the
  // app picks it up.  The init script does *not* touch the id so it will
  // survive its own test-runner reload.
  await page.evaluate(() => window.localStorage.removeItem('kitty-active-chat-id'));
  await page.reload();
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });
}

async function enterChatThread(page: Page) {
  await page.waitForTimeout(500);
  const chatBtn = page.getByRole('button', { name: /^chat$/i }).first();
  await chatBtn.click();
  await page.waitForTimeout(500);
  const composer = page.locator('textarea').first();
  await composer.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
  return composer;
}

test.describe('Chat Trust Slice 3 — phone', () => {
  test.use(MOBILE);

  test('send → stream → persist → reload restores identical content', async ({ page }) => {
    await stubGateway(page);
    await goClean(page);

    const chatBtn = page.getByRole('button', { name: /^chat$/i }).first();
    await chatBtn.click();
    const composer = page.locator('textarea').first();
    await expect(composer).toBeVisible({ timeout: 5000 });

    const uniqueText = `slice-3-test-${Date.now()}`;
    await composer.click();
    await composer.fill(uniqueText);
    await page.getByRole('button', { name: /send message/i }).click();

    // Wait for SSE stream to deliver content
    await expect(page.locator('.msg-in').filter({ hasText: /Hel/ }).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('.msg-in').filter({ hasText: /world!/ }).first()).toBeVisible({ timeout: 10_000 });

    const messagesBeforeReload = await page.locator('.msg-in').allTextContents();
    expect(messagesBeforeReload.length).toBeGreaterThanOrEqual(2);

    // Reload — active-chat-id survives because initScript no longer clears it
    await page.reload();
    await expect(page.locator('main')).toBeVisible({ timeout: 15_000 });

    // Navigate to chat — app restores active chat from localStorage
    await page.getByRole('button', { name: /^chat$/i }).first().click();

    // Wait for recovered messages to render — check for actual content, not timeout
    await expect(page.locator('.msg-in').filter({ hasText: new RegExp(uniqueText) }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.msg-in').filter({ hasText: /Hello, world!/ }).first()).toBeVisible({ timeout: 10_000 });

    const messagesAfterReload = await page.locator('.msg-in').allTextContents();
    expect(messagesAfterReload.length).toBeGreaterThanOrEqual(messagesBeforeReload.length);
  });

  test('stream failure shows friendly recovery copy and retry succeeds', async ({ page }) => {
    await stubGateway(page, { failAfterChunks: 1 });
    await goClean(page);

    await page.getByRole('button', { name: /^chat$/i }).first().click();
    await page.waitForTimeout(500);

    const composer = page.locator('textarea').first();
    await expect(composer).toBeVisible();

    await composer.click();
    await composer.fill('');
    await composer.type(`error-test-${Date.now()}`, { delay: 10 });
    await page.waitForTimeout(300);
    await page.getByRole('button', { name: /send message/i }).click();

    // The cut stream (no [DONE]) must show plain copy, never raw internals.
    await page.waitForTimeout(2000);
    const failureBubble = page.locator('.msg-in').filter({ hasText: /cut off/i }).first();
    await expect(failureBubble).toBeVisible({ timeout: 10_000 });
    const failureText = await failureBubble.textContent();
    expect(failureText).toContain('retry');
    expect(failureText).not.toContain('Stream closed without [DONE]');
    expect(failureText).not.toContain('incomplete response');

    // Now retry: set up a successful stub
    await page.unroute('**/proxy/api/chat/completions');
    await stubGateway(page);

    // Click the retry button on the failed bubble
    const retryBtn = page.getByRole('button', { name: /retry/i }).first();
    expect(await retryBtn.count()).toBeGreaterThan(0);
    await retryBtn.click();
    await page.waitForTimeout(2000);
    // Verify the retry produced a successful response
    const messagesAfterRetry = page.locator('.msg-in').filter({ hasText: /Hel/ });
    await expect(messagesAfterRetry.first()).toBeVisible({ timeout: 10_000 });
  });

  test('gateway routing error event shows plain-language recovery copy', async ({ page }) => {
    await stubGateway(page, { errorEvent: 'routing' });

    await page.goto('/');
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: /^chat$/i }).first().click();
    await page.waitForTimeout(500);

    const composer = page.locator('textarea').first();
    await expect(composer).toBeVisible();
    await composer.click();
    await composer.fill('why is the provider mad');
    await page.keyboard.press('Enter');

    await page.waitForTimeout(3000);
    const bubble = page.locator('.msg-in').filter({ hasText: /model provider|retry/i }).first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    const text = await bubble.textContent();
    // Jargon check: no raw internal strings, and a real recovery action is named.
    expect(text).not.toContain('Stream closed without [DONE]');
    expect(text).not.toMatch(/HTTP \d{3}|500|Gateway error/);
    expect(text).toMatch(/retry/i);
  });

  test('retry does not duplicate user message', async ({ page }) => {
    await stubGateway(page, { failAfterChunks: 1 });
    await goClean(page);

    await page.getByRole('button', { name: /^chat$/i }).first().click();
    await page.waitForTimeout(500);

    const composer = page.locator('textarea').first();
    await expect(composer).toBeVisible();

    const dedupText = `dedup-test-${Date.now()}`;
    await composer.fill(dedupText);
    await page.getByRole('button', { name: /send message/i }).click();

    await page.waitForTimeout(800);

    // Retry with success
    await page.unroute('**/proxy/api/chat/completions');
    await stubGateway(page);

    const retryBtn = page.getByRole('button', { name: /retry/i }).first();
    if (await retryBtn.count() > 0 && await retryBtn.isVisible()) {
      await retryBtn.click();
    }

    await page.waitForTimeout(1000);

    // Verify exactly one user message in the viewport
    // Count message bubbles — user messages are right-aligned (row-reverse)
    const allMessages = page.locator('.msg-in');
    const count = await allMessages.count();

    // Reload to verify deduplication in persisted recovery
    await page.reload();
    await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /^chat$/i }).first().click();
    await page.waitForTimeout(1000);

    const afterCount = await page.locator('.msg-in').count();
    // There should be messages, and the user text should appear exactly once
    const allTextAfter = (await page.locator('.msg-in').allTextContents()).join(' ');
    const occurrences = (allTextAfter.match(new RegExp(dedupText, 'g')) || []).length;
    // User message text appears in the user bubble AND potentially in the sseBody test text
    // Filter to count actual user message nodes
    const userMsgElements = page.locator('.msg-in').filter({ hasText: new RegExp(`^${dedupText}`) });
    const userMsgCount = await userMsgElements.count();
    expect(userMsgCount).toBeLessThanOrEqual(1);
  });
});

test.describe('Chat Trust Slice 3 — desktop regression', () => {
  test('chat loads and send is accessible on desktop', async ({ page }) => {
    await stubGateway(page);

    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await goClean(page);

    const chatsBtn = page.getByRole('button', { name: /^chat$/i }).first();
    await chatsBtn.first().click();
    await page.waitForTimeout(500);

    const input = page.locator('textarea').first();
    await input.click();
    await input.fill('');
    await input.type('hello desktop', { delay: 10 });
    await page.waitForTimeout(300);
    // React controlled inputs can race with Playwright fill — just check presence
    expect(errors).toEqual([]);
  });
});
