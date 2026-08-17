import { afterEach, describe, expect, it, vi } from 'vitest'

const originalPort = process.env.PLAYWRIGHT_PORT
const originalReuse = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER

// Importing Playwright's config through Vitest/Vite is normally sub-second, but
// module-transform contention in a cold full suite has reached ~13s on the M1 CI-parity host.
// Keep generous headroom scoped to these two dynamic-import tests only; the isolated import remains sub-second.
const CONFIG_LOAD_TIMEOUT_MS = 30_000

async function loadConfig() {
  vi.resetModules()
  return (await import('../playwright.config')).default
}

afterEach(() => {
  if (originalPort === undefined) delete process.env.PLAYWRIGHT_PORT
  else process.env.PLAYWRIGHT_PORT = originalPort
  if (originalReuse === undefined) delete process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER
  else process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER = originalReuse
})

describe('Playwright smoke server ownership', () => {
  it('defaults to an isolated local server instead of reusing port 4000', async () => {
    delete process.env.PLAYWRIGHT_PORT
    delete process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER

    const config = await loadConfig()
    const webServer = config.webServer as Exclude<typeof config.webServer, undefined>

    expect(config.use?.baseURL).toBe('http://127.0.0.1:4100')
    expect(config.retries).toBe(1)
    expect(config.failOnFlakyTests).toBe(true)
    expect(Array.isArray(webServer)).toBe(false)
    if (Array.isArray(webServer)) throw new Error('expected one smoke webServer')
    expect(webServer.port).toBe(4100)
    expect(webServer.reuseExistingServer).toBe(false)
    expect(webServer.command).toContain('-p 4100')
  }, CONFIG_LOAD_TIMEOUT_MS)

  it('allows CI to explicitly reuse its checkout-owned port 4000 server', async () => {
    process.env.PLAYWRIGHT_PORT = '4000'
    process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER = '1'

    const config = await loadConfig()
    const webServer = config.webServer as Exclude<typeof config.webServer, undefined>

    expect(config.use?.baseURL).toBe('http://127.0.0.1:4000')
    expect(Array.isArray(webServer)).toBe(false)
    if (Array.isArray(webServer)) throw new Error('expected one smoke webServer')
    expect(webServer.port).toBe(4000)
    expect(webServer.reuseExistingServer).toBe(true)
  }, CONFIG_LOAD_TIMEOUT_MS)
})
