from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))


gateway = ROOT / "gateway/kitty-chat/src/lib/gateway.ts"
old_gateway = '''    const liveIds = new Set(ids)
    let models: Model[]
    try {
      const picker = await fetchModelPicker()
      models = buildPickerModels(picker).filter(model => liveIds.has(model.id))
    } catch {
      models = MODELS.filter(model => liveIds.has(model.id))
    }
    return {
      models,
      fromLiveGateway: true,
      error: null,
    }
'''
new_gateway = '''    const liveIds = new Set(ids)
    let picker
    try {
      const controller = new AbortController()
      const timeoutId = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
      try {
        picker = await fetchModelPicker(controller.signal)
      } finally {
        window.clearTimeout(timeoutId)
      }
    } catch (err) {
      const models = MODELS.filter(model => liveIds.has(model.id))
      const error = err instanceof Error && err.name === 'AbortError'
        ? 'Model details timed out — retry to reconnect to Kitty.'
        : `Model details unavailable — ${describeFetchError(err, null)}. Retry to reconnect to Kitty.`
      return {
        models,
        fromLiveGateway: false,
        error,
      }
    }

    const models = buildPickerModels(picker).filter(model => liveIds.has(model.id))
    if (models.length === 0) {
      return {
        models: [],
        fromLiveGateway: false,
        error: 'No live curated models are available — retry to reconnect to Kitty.',
      }
    }
    return {
      models,
      fromLiveGateway: true,
      error: null,
    }
'''
replace_once(gateway, old_gateway, new_gateway)

page = ROOT / "gateway/kitty-chat/src/app/page.tsx"
replace_once(
    page,
    "  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)\n",
    "  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)\n"
    "  const modelUnavailable = !k.modelGateway.live || k.availableModels.length === 0\n",
)
replace_once(
    page,
    "        activeModel={k.activeModel} onSend={k.handleRuntimeSend}\n"
    "        onCancel={k.handleStop} onReload={k.handleRetry}\n",
    "        activeModel={k.activeModel} onSend={(text) => { if (!modelUnavailable) k.handleRuntimeSend(text) }}\n"
    "        onCancel={k.handleStop} onReload={() => { if (!modelUnavailable) k.handleRetry() }}\n",
)
replace_once(
    page,
    "                onRetry: k.handleRetry,\n",
    "                onRetry: () => { if (!modelUnavailable) k.handleRetry() },\n",
)
replace_once(
    page,
    "              onSend={k.handleSend}\n"
    "              onStop={k.handleStop}\n"
    "              isStreaming={k.isStreaming}\n"
    "              disabled={k.isStreaming}\n",
    "              onSend={() => { if (!modelUnavailable) k.handleSend() }}\n"
    "              onStop={k.handleStop}\n"
    "              isStreaming={k.isStreaming}\n"
    "              disabled={k.isStreaming || modelUnavailable}\n",
)

gateway_test = ROOT / "gateway/kitty-chat/tests/gatewayIntegration.test.tsx"
replace_once(
    gateway_test,
    "  it('keeps a live safe route when curated metadata is temporarily unavailable', async () => {\n",
    "  it('keeps a safe route but reports degraded state when curated metadata is unavailable', async () => {\n",
)
replace_once(
    gateway_test,
    "    expect(result.fromLiveGateway).toBe(true)\n"
    "    expect(result.error).toBeNull()\n"
    "    expect(result.models.map(model => [model.id, model.name])).toEqual([['kitty-code', 'Code']])\n",
    "    expect(result.fromLiveGateway).toBe(false)\n"
    "    expect(result.error).toMatch(/model details unavailable/i)\n"
    "    expect(result.models.map(model => [model.id, model.name])).toEqual([['kitty-code', 'Code']])\n",
)

page_test = ROOT / "gateway/kitty-chat/tests/PageSurfaceLayout.test.ts"
replace_once(
    page_test,
    "    expect(composer).toContain('onSend={k.handleSend}')\n",
    "    expect(composer).toContain('onSend={() => { if (!modelUnavailable) k.handleSend() }}')\n"
    "    expect(composer).toContain('disabled={k.isStreaming || modelUnavailable}')\n",
)

print("PR #672 fail-closed patch applied")
