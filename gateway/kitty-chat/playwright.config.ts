import { defineConfig, devices } from '@playwright/test';

// Container images often ship a Chromium that predates the pinned Playwright
// build. Point at it rather than downloading a second copy on every run.
const launchOptions = process.env.PLAYWRIGHT_CHROMIUM_PATH
  ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
  : undefined;

export default defineConfig({
  testDir: './tests/smoke',
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:4000',
    trace: 'on-first-retry',
    ...(launchOptions ? { launchOptions } : {}),
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile',
      use: {
        ...devices['iPhone 14'],
        // Use Chromium for mobile to avoid needing WebKit installed
        browserName: 'chromium',
      },
    },
  ],
  webServer: {
    command: 'npm run start',
    port: 4000,
    timeout: 30_000,
    reuseExistingServer: true,
  },
});
