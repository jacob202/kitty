import { expect, test } from '@playwright/test'

/**
 * BUILDER-001 acceptance: Chat → Builder proposal → approve → durable packet.
 *
 * Drives the REAL running app (gateway :8000, UI :4000) — not stubs — through
 * the full journey the PC-BUILDER contract requires:
 *
 *  1. Navigate to Work, find the "Ask Builder" request field.
 *  2. Type a plain-language bounded request.
 *  3. Click "Prepare Builder proposal" — a bounded proposal appears.
 *  4. Click "Compile as Builder Mission" — a prepared mission appears.
 *  5. Click "Approve" with confirmation — a durable packet is created.
 *  6. The approved job is visible (state=accepted).
 *
 * Runs at desktop 1440×1000 and iPhone-class 393×852 via the projects in
 * playwright.config.ts. Requires the real gateway with an available model
 * provider (OpenRouter DeepSeek Flash v4 via kitty-small).
 */

const REQUEST_TEXT = 'Add a one-line hello-world greeting to the top of the README file'

test('BUILDER-001: plain-language request reaches a bounded approved packet', async ({ page }, testInfo) => {
  test.setTimeout(180_000) // compile calls a real model provider; give it room
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))

  await page.addInitScript(() => window.localStorage.setItem('kitty-onboarded', 'true'))
  await page.goto('/', { waitUntil: 'load' })
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })

  // Navigate to Work — the surface that owns the Ask Builder request field.
  await page.getByRole('button', { name: 'Work', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Work' })).toBeVisible({ timeout: 10_000 })

  // The "Ask Builder" section must be visible (defect 3: Work was status-only).
  await expect(page.getByText('Ask Builder').first()).toBeVisible({ timeout: 10_000 })

  // Type a plain-language bounded request into the Ask Builder textarea.
  const requestInput = page.getByRole('textbox', { name: 'Ask Builder for work' })
  await expect(requestInput).toBeVisible()
  await requestInput.fill(REQUEST_TEXT)

  // Click "Prepare Builder proposal" — this calls /builder/conversation/compile
  // which shapes the request into a bounded task using the model route (defect 1).
  const prepareButton = page.getByRole('button', { name: /prepare.*proposal/i })
  await expect(prepareButton).toBeEnabled()
  await prepareButton.click()

  // The button shows "Preparing…" while the model provider shapes the request
  // (~10s with OpenRouter DeepSeek Flash v4). Then a BUILDER PROPOSAL card appears.
  await expect(page.getByText('BUILDER PROPOSAL').first()).toBeVisible({ timeout: 90_000 })

  // Screenshot for evidence: the proposal card is on screen
  await page.screenshot({ path: `test-results/builder-001-proposal-${testInfo.project.name}.png`, fullPage: true })

  // The proposal must show the request's content in some form.
  await expect(page.getByText(/hello.*world/i).first()).toBeVisible({ timeout: 5_000 })

  // Click "Compile as Builder Mission" — this calls /builder/conversation/propose.
  const compileButton = page.getByRole('button', { name: /compile.*mission/i })
  await expect(compileButton).toBeVisible({ timeout: 5_000 })
  await compileButton.click()

  // After compilation, an approve control must appear.
  await expect(page.getByRole('button', { name: /approve/i }).first()).toBeVisible({ timeout: 90_000 })

  // Screenshot: the prepared mission ready for approval
  await page.screenshot({ path: `test-results/builder-001-prepared-${testInfo.project.name}.png`, fullPage: true })

  // Approve the mission — this calls /builder/conversation/approve with confirmed=true.
  // The durable packet is created (state=accepted, apply_status=created).
  const approveButton = page.getByRole('button', { name: /approve/i }).first()
  await expect(approveButton).toBeEnabled({ timeout: 5_000 })
  await approveButton.click()

  // If there's a confirmation dialog, confirm it.
  const confirmButton = page.getByRole('button', { name: /^(confirm|yes|approve)$/i }).filter({ hasNotText: /cancel/i }).last()
  if (await confirmButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await confirmButton.click()
  }

  // The job must reach an accepted/durable state — not a dead-end error.
  // Look for accepted state text or the resumed-job view.
  const acceptedIndicator = page.getByText(/accepted|in.progress|running|mission.*accepted/i).first()
  await expect(acceptedIndicator).toBeVisible({ timeout: 30_000 })

  // Screenshot: the accepted durable packet
  await page.screenshot({ path: `test-results/builder-001-accepted-${testInfo.project.name}.png`, fullPage: true })

  // No horizontal overflow at either viewport (mobile regression guard).
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow, `horizontal overflow ${overflow}px at ${testInfo.project.name}`).toBeLessThanOrEqual(0)

  expect(errors, `page errors: ${errors.join(' | ')}`).toEqual([])
})
