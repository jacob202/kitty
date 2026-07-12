import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/smoke',
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:4000',
    trace: 'on-first-retry',
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
