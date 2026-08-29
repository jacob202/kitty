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

print("PR #672 fail-closed patch applied")
