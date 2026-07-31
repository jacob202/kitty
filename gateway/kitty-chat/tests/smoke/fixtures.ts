import { test as base, expect } from '@playwright/test'

// The smoke suite runs the Next server alone, with no Python gateway behind it.
// HealthGate blocks rendering until /proxy/health answers, so without this stub
// <main> never mounts and every spec times out waiting for it. These specs
// exercise the UI, not the gateway handshake.
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/proxy/health', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    )
    await use(page)
  },
})

export { expect }
