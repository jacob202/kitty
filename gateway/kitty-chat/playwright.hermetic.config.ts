import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

const uiPort = 4110
const gatewayPort = 48100
const llmPort = 48101
const dataRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'kitty-hermetic-gateway-'))
const python = process.env.KITTY_HERMETIC_PYTHON ?? 'python3.12'
const secret = 'hermetic-gateway-secret'
const repoRoot = path.resolve(process.cwd(), '../..')
const guardPath = path.join(repoRoot, 'tests/python_startup')

export default defineConfig({
  testDir: './tests/smoke',
  testMatch: 'chat-real-gateway.spec.ts',
  timeout: 45_000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${uiPort}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'hermetic-chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'node tests/support/fake-litellm.mjs',
      url: `http://127.0.0.1:${llmPort}/health`,
      reuseExistingServer: false,
      timeout: 20_000,
      env: { ...process.env, KITTY_FAKE_LITELLM_PORT: String(llmPort) },
    },
    {
      command: `cd ../.. && ${python} -m uvicorn --app-dir gateway/kitty-chat/tests/support hermetic_gateway:app --host 127.0.0.1 --port ${gatewayPort}`,
      url: `http://127.0.0.1:${gatewayPort}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        ...process.env,
        KITTY_ENV: 'test',
        KITTY_TEST_GUARD: '1',
        PYTHONPATH: [guardPath, repoRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
        KITTY_DATA_ROOT: dataRoot,
        GATEWAY_SECRET: secret,
        LITELLM_BASE: `http://127.0.0.1:${llmPort}`,
        LITELLM_KEY: 'hermetic-litellm-key',
        OPENAI_API_KEY: '',
        ANTHROPIC_API_KEY: '',
        OPENROUTER_API_KEY: '',
        GEMINI_API_KEY: '',
      },
    },
    {
      command: `node node_modules/next/dist/bin/next start -H 127.0.0.1 -p ${uiPort}`,
      port: uiPort,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        ...process.env,
        KITTY_GATEWAY_URL: `http://127.0.0.1:${gatewayPort}`,
        KITTY_GATEWAY_SECRET: secret,
        GATEWAY_SECRET: secret,
      },
    },
  ],
})
