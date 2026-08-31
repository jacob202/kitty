import { test, expect } from './fixtures'

async function assertNoHorizontalOverflow(page: import('@playwright/test').Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true)
}

async function assertControlAboveMobileBar(page: import('@playwright/test').Page, locator: import('@playwright/test').Locator) {
  if (page.viewportSize()?.width && page.viewportSize()!.width < 600) {
    await locator.scrollIntoViewIfNeeded()
    const bar = await page.getByRole('navigation', { name: 'Main navigation' }).boundingBox()
    const control = await locator.boundingBox()
    expect(control).not.toBeNull()
    expect(bar).not.toBeNull()
    expect(control!.y + control!.height).toBeLessThanOrEqual(bar!.y)
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('kitty-onboarded', 'true'))
  await page.route('**/proxy/todos', route => route.fulfill({ json: { todos: [{ id: 3, content: 'check launch', status: 'pending' }] } }))
  await page.route('**/proxy/todos/3/complete', route => route.fulfill({ status: 200, json: {} }))
  await page.route('**/proxy/monitors', route => route.fulfill({ json: { watches: [{ id: 'm-1', url: 'https://example.com', label: 'Example', last_match: null }] } }))
  await page.route('**/proxy/monitor/m-1', route => route.fulfill({ status: 200, json: { deleted: 'm-1' } }))
})

test('Tasks and Automations mount todo and monitor controls', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Open tasks' }).click()
  await expect(page.getByPlaceholder('add a todo…')).toBeVisible()
  const complete = page.getByRole('button', { name: /complete/i })
  await assertControlAboveMobileBar(page, complete)
  const completeRequest = page.waitForRequest(request => request.method() === 'POST' && new URL(request.url()).pathname === '/proxy/todos/3/complete')
  await complete.click()
  await completeRequest
  await assertNoHorizontalOverflow(page)

  if (page.viewportSize()?.width && page.viewportSize()!.width < 600) {
    await page.getByRole('button', { name: 'More' }).click()
    await page.getByRole('menuitem', { name: 'Automations' }).click()
  } else {
    await page.getByRole('button', { name: 'Automations' }).click()
  }
  await expect(page.getByRole('heading', { name: 'Monitors' })).toBeVisible()
  const remove = page.getByRole('button', { name: /remove monitor/i })
  await assertControlAboveMobileBar(page, remove)
  const removeRequest = page.waitForRequest(request => request.method() === 'DELETE' && new URL(request.url()).pathname === '/proxy/monitor/m-1')
  await remove.click()
  await removeRequest
  await assertNoHorizontalOverflow(page)
})
