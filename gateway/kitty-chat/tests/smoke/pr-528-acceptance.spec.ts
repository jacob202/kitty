import { expect, test, type Page, type Route } from '@playwright/test'

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 393, height: 852 },
] as const

const MODEL_IDS = [
  'kitty-default',
  'kitty-small',
  'kitty-think',
  'kitty-code',
  'kitty-vision',
]

const DISPLAY_NAMES: Record<string, string> = {
  'kitty-default': 'Daily Kitty',
  'kitty-small': 'Quick',
  'kitty-think': 'Think',
  'kitty-code': 'Code',
  'kitty-vision': 'Vision',
}

const PROVIDER_DISPATCH_PATH = /\/(?:api\/chat\/completions|studio\/(?:agent|generate|plan)|image\/generate|mcp\/imagen)(?:\/|$)/
const STUDIO_BATCH_CREATE_PATH = /\/studio\/batches$/

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

function runtimeManifest() {
  const fact = <T>(value: T) => ({ state: 'available', value, reason: null })
  return {
    schema_version: 1,
    manifest_id: 'pr-528-acceptance',
    revision: 'hermetic-pr-528',
    generated_at: '2026-08-21T00:00:00Z',
    valid_until: '2026-08-22T00:00:00Z',
    application: {
      name: 'Kitty', version: fact('test'), build_commit: null, environment: 'test',
    },
    clock: fact({ current_time: '2026-08-21T00:00:00Z', timezone: 'UTC' }),
    context: { active_project: fact(null), repository: fact(null) },
    execution: { builder: fact(null) },
    inference: {
      routing_mode: 'curated', available_models: fact(MODEL_IDS), providers: [],
      execution_location: 'hermetic',
    },
    tools: fact([]),
    connections: { gateway: fact({}), litellm: fact({}) },
    approvals: fact({}),
  }
}

function pickerPayload() {
  const roles = ['auto', 'fast', 'think', 'code', 'vision']
  return {
    schema_version: 1,
    source: 'hermetic-pr-528',
    discovery: { state: 'available', reason: null, checked_at: '2026-08-21T00:00:00Z' },
    claims: { role_tags: 'curated', alternatives: 'disabled' },
    presets: MODEL_IDS.map((route, index) => ({
      role: roles[index], label: DISPLAY_NAMES[route], route,
      purpose: index === 0 ? 'Choose the right lane.' : 'Curated Kitty choice.',
      kind: index === 0 ? 'router' : 'model_role', provider: null, model: null, configured: true,
      catalogue: null, catalogue_state: 'unknown', alternatives: [],
    })),
  }
}

function healthSurfacePayload() {
  const names = [
    'gateway', 'database', 'memory', 'automation_supervisor', 'cron', 'telegram',
    'image_lab', 'image_providers', 'image_queue', 'ollama', 'pending_grants',
  ]
  return {
    ok: true,
    generated_at: '2026-08-21T00:00:00Z',
    overall: 'healthy',
    domains: names.map(name => ({ name, status: 'available', reason: '', detail: {} })),
    degraded: [],
    still_functional: names,
    pending_grants: 0,
  }
}

async function installHermeticStubs(
  page: Page,
  providerDispatches: string[],
  controlPlaneWrites: string[],
  unexpectedPaths: string[],
) {
  await page.route('**/proxy/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace(/^\/proxy/, '')
    const method = request.method()

    if (method === 'POST' && (PROVIDER_DISPATCH_PATH.test(path) || STUDIO_BATCH_CREATE_PATH.test(path))) {
      providerDispatches.push(`${method} ${path}`)
    }
    if (method !== 'GET' && path !== '/studio/estimate' && !PROVIDER_DISPATCH_PATH.test(path) && !STUDIO_BATCH_CREATE_PATH.test(path)) {
      controlPlaneWrites.push(`${method} ${path}`)
    }
    if (path === '/repairs') return route.continue()
    if (path === '/health') return json(route, { status: 'ok', litellm_reachable: true })
    if (path === '/health/surface') return json(route, healthSurfacePayload())
    if (path === '/brief') {
      return json(route, {
        date: '2026-08-21', headlines: [], memory_snippet: '', intention: '',
        generated_at: '2026-08-21T00:00:00Z', notification_sent: false, error: null,
      })
    }
    if (path === '/weather') return json(route, { error: 'unavailable' })
    if (path === '/api/models') {
      return json(route, { data: MODEL_IDS.map(id => ({ id, display_name: DISPLAY_NAMES[id] })) })
    }
    if (path === '/models/picker') return json(route, pickerPayload())
    if (path === '/api/providers') return json(route, { active: 'auto', order: [], providers: [], warnings: [], config_path: 'hermetic' })
    if (path.startsWith('/runtime/manifest')) return json(route, runtimeManifest())
    if (path === '/chats') return json(route, { chats: [] })
    if (path === '/signals') return json(route, { ok: true, checks_run: 0, issues: 0, repairs: [] })
    if (path === '/state/changes') {
      return json(route, { baseline_ts: null, current_ts: 0, changes: [], new_signals: [] })
    }
    if (path === '/state/now') return json(route, { ts: 0, sections: { inbox: { ok: true, untriaged_count: 0 } } })
    if (path === '/todos') return json(route, { todos: [] })
    if (path === '/session/context') {
      return json(route, {
        current_branch: null, last_session_topic: null, open_threads: [], next_actions: [],
      })
    }
    if (path === '/actions') return json(route, { actions: [] })
    if (path === '/activity') return json(route, {
      items: [],
      counts: { total: 0, waiting: 0, running: 0, failed: 0, completed: 0 },
      sources: {},
    })
    if (path === '/artifacts') return json(route, { artifacts: [] })
    if (path === '/intelligence') return json(route, {
      items: [],
      counts: { shown: 0, total_candidates: 0 },
      sources: {},
    })
    if (path === '/inbox/triaged') return json(route, { entries: [] })
    if (path === '/projects') return json(route, { projects: [] })
    if (path === '/projects/next-steps') return json(route, [])
    if (path === '/context/project') return json(route, { project: null })
    if (path === '/deadlines') return json(route, { deadlines: [] })
    if (path === '/network/tailnet') return json(route, { ok: false, tailnet_ip: null, ui_url: null })
    if (path === '/knowledge/experts') return json(route, { experts: [] })
    if (path === '/insight-loop/due') return json(route, { insights: [] })
    if (path === '/loops') return json(route, { loops: [] })
    if (path === '/insights') return json(route, { insights: [] })
    if (path === '/prompts') return json(route, { templates: [] })
    if (path === '/image/status') {
      return json(route, {
        available: false,
        backend: 'comfyui',
        engines: [
          { name: 'comfyui', label: 'ComfyUI', available: false },
          { name: 'drawthings', label: 'Draw Things', available: false },
        ],
      })
    }
    if (path === '/studio/characters') {
      return json(route, { characters: [] })
    }
    if (path === '/studio/estimate') {
      return json(route, {
        estimate: {
          cost: { state: 'unknown', usd: null, basis: 'offline', samples: 0 },
          duration: { state: 'unknown', seconds: null, basis: 'offline', samples: 0 },
        },
      })
    }
    unexpectedPaths.push(`${method} ${path}`)
    return json(route, { error: `Unexpected hermetic request: ${method} ${path}` }, 501)
  })
}

async function assertNoHorizontalOverflow(page: Page) {
  const size = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(size.scroll).toBeLessThanOrEqual(size.client + 1)
}

for (const viewport of VIEWPORTS) {
  test(`PR #528 product acceptance at ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'hermetic-chromium', 'runs only with isolated Kitty state')
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.addInitScript(() => {
      window.localStorage.setItem('kitty-onboarded', 'true')
      window.localStorage.removeItem('kitty-image-lab-session')
    })
    const providerDispatches: string[] = []
    const controlPlaneWrites: string[] = []
    const unexpectedPaths: string[] = []
    await installHermeticStubs(page, providerDispatches, controlPlaneWrites, unexpectedPaths)

    await page.goto('/')
    const main = page.locator('main')
    await expect(main).toBeVisible({ timeout: 15_000 })

    await expect(main.getByText("Kitty's core service is unavailable")).toBeVisible()
    await expect(main.getByText('Memory search is temporarily unavailable')).toBeVisible()
    await expect(main.getByText('A background service needs setup', { exact: true })).toBeVisible()
    await expect(main.getByText('Search indexing needs attention').first()).toBeVisible()
    const homeText = (await main.innerText()).toLowerCase()
    for (const forbidden of [
      '/users/', '.env', 'openai_api_key', 'python3.11', 'python -m venv', 'venv/bin',
      'memory client request', 'status code 503', 'daemon index handshake', 'codegraph', 'mem0', 'gateway',
    ]) {
      expect(homeText, `Home leaked ${forbidden}`).not.toContain(forbidden)
    }
    await assertNoHorizontalOverflow(page)

    const modelButton = page.getByRole('button', { name: 'Model: Daily Kitty' })
    await expect(modelButton).toBeEnabled()
    await modelButton.click()
    const pickerInput = page.getByPlaceholder('search the shortlist…')
    await expect(pickerInput).toBeVisible()
    const picker = pickerInput.locator('xpath=../..')
    const surface = await picker.evaluate((element) => {
      const box = element.getBoundingClientRect()
      const color = getComputedStyle(element).backgroundColor
      const rgba = color.match(/rgba?\(([^)]+)\)/)?.[1].split(',').map(part => part.trim()) ?? []
      const alpha = rgba.length === 4 ? Number(rgba[3]) : 1
      const top = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
      return {
        alpha, zIndex: Number(getComputedStyle(element).zIndex),
        left: box.left, right: box.right, top: box.top, bottom: box.bottom,
        viewportWidth: window.innerWidth, viewportHeight: window.innerHeight,
        topmost: top !== null && element.contains(top),
      }
    })
    expect(surface.alpha).toBe(1)
    expect(surface.zIndex).toBeGreaterThan(50)
    expect(surface.topmost).toBe(true)
    expect(surface.left).toBeGreaterThanOrEqual(0)
    expect(surface.right).toBeLessThanOrEqual(surface.viewportWidth + 1)
    expect(surface.top).toBeGreaterThanOrEqual(0)
    expect(surface.bottom).toBeLessThanOrEqual(surface.viewportHeight + 1)
    const options = picker.getByRole('option')
    await expect(options).toHaveCount(MODEL_IDS.length)
    for (const label of Object.values(DISPLAY_NAMES)) await expect(picker.getByText(label).first()).toBeVisible()
    await assertNoHorizontalOverflow(page)

    await page.keyboard.press('Escape')
    await page.getByRole('button', { name: /^image lab$/i }).first().click()
    const lab = page.getByRole('region', { name: 'Image Lab' })
    await expect(lab).toBeVisible()
    await expect(lab.getByText(/no image engine is online/i)).toBeVisible()
    const composer = lab.getByPlaceholder(/tell kitty what you want to make or change/i)
    await expect(composer).toBeVisible()
    await composer.fill('a sleeping cat')
    await expect(lab.getByTestId('image-lab-send')).toBeDisabled()
    const checkAgain = lab.getByRole('button', { name: 'check again' })
    await expect(checkAgain).toBeVisible()
    await checkAgain.click()
    await expect(lab.getByTestId('image-lab-send')).toBeDisabled()
    await expect(lab.getByText(/internal server error|provider dispatch|status code/i)).toHaveCount(0)
    await assertNoHorizontalOverflow(page)

    if (viewport.name === 'mobile') {
      const nav = page.getByRole('navigation', { name: 'Main navigation' })
      const box = await nav.boundingBox()
      expect(box).not.toBeNull()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
    }
    expect(providerDispatches, 'acceptance must not dispatch chat completions or provider/renderer work').toEqual([])
    expect(controlPlaneWrites, 'acceptance must not create sessions, batches, or other control-plane work').toEqual([])
    expect(unexpectedPaths, 'all hermetic Home requests must have explicit response shapes').toEqual([])
  })
}
