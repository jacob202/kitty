import { defineConfig, devices } from '@playwright/test';

// Container images often ship a Chromium that predates the pinned Playwright
// build. Point at it rather than downloading a second copy on every run.
const launchOptions = process.env.PLAYWRIGHT_CHROMIUM_PATH
  ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
  : undefined;

const smokePort = Number.parseInt(process.env.PLAYWRIGHT_PORT ?? '4100', 10);
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === '1';
const smokeBaseUrl = `http://127.0.0.1:${smokePort}`;

export default defineConfig({
  testDir: './tests/smoke',
  timeout: 30_000,
  retries: 1,
  failOnFlakyTests: true,
  use: {
    baseURL: smokeBaseUrl,
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
    command: `node node_modules/next/dist/bin/next start -H 127.0.0.1 -p ${smokePort}`,
    port: smokePort,
    timeout: 30_000,
    reuseExistingServer,
  },
});
