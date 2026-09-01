import { test, expect } from './fixtures'

const emptyDeadlines = { deadlines: [] }

function sweepResult(delivered: boolean) {
  return {
    found: 1,
    open: 1,
    needs_jacob: 0,
    top: null,
    blind_spots: [],
    generated_at: '2026-08-31T12:00:00-06:00',
    escalated: delivered ? 1 : 0,
    escalation_failed: delivered ? 0 : 1,
    delivery_status: delivered ? 'delivered' : 'source_unavailable',
    delivery_message: delivered
      ? '1 deadline warning delivered.'
      : 'A deadline warning was due, but nothing was delivered. Check notification setup and try again.',
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('kitty-onboarded', 'true'))
})
async function stubDeadlineApi(page: import('@playwright/test').Page, delivered: boolean) {
  await page.route('**/proxy/deadlines**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname === '/proxy/deadlines') {
      await route.fulfill({ json: emptyDeadlines })
      return
    }
    if (request.method() === 'POST' && url.pathname === '/proxy/deadlines/sweep') {
      await route.fulfill({ json: sweepResult(delivered) })
      return
    }
    await route.continue()
  })
}

test('Home sweep reports the number of warnings actually delivered', async ({ page }) => {
  await stubDeadlineApi(page, true)
  await page.goto('/')
  await page.getByRole('button', { name: 'sweep', exact: true }).click()
  await expect(page.getByText('1 deadline warning delivered.')).toBeVisible()
})

test('Home sweep says plainly when no notification channel delivered the warning', async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 })
  await stubDeadlineApi(page, false)
  await page.goto('/')
  const sweep = page.getByRole('button', { name: 'sweep', exact: true })
  await sweep.scrollIntoViewIfNeeded()
  await sweep.click()
  await expect(page.getByText(/nothing was delivered/i)).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    ),
  ).toBe(true)
})
