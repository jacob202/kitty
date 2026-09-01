import { randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const root = process.env.KITTY_DSH_PACKAGE_ROOT
if (!root) throw new Error('KITTY_DSH_PACKAGE_ROOT is required')
const requireFromDsh = createRequire(pathToFileURL(`${root}/package.json`))
const load = async (name) => import(pathToFileURL(requireFromDsh.resolve(name)).href)
const [{ installModelSelection }, { createUserMessage }, { SessionId }, schema] = await Promise.all([
  load('@deepseek-ai/dsh-agent'),
  load('@deepseek-ai/dsh-llm'),
  load('@deepseek-ai/dsh-session'),
  load('@deepseek-ai/schemastery'),
])
const z = schema.default ?? schema

export const name = 'kitty-headless-runner'
export const inject = ['agentDefaultModel', 'agents', 'sessions', 'agentPresets']
export const Config = z.object({ task: z.string().required() })

function summarize(events, firstSeq) {
  let started = false
  let text = ''
  let reason
  for (const event of events) {
    if (event.seq < firstSeq) continue
    if (event.type === 'turn/start') {
      started = true
      continue
    }
    if (!started) continue
    if (event.type === 'assistant/message') {
      const joined = event.data.message.content
        .filter((block) => block.type === 'text')
        .map((block) => block.text)
        .join('')
      if (joined) text = joined
    }
    if (event.type === 'turn/end') reason = event.data.reason
  }
  return { text, reason }
}

export function apply(ctx, config) {
  const exit = ctx.get('appExit')
  if (!exit) throw new Error('kitty-headless-runner requires appExit')

  ;(async () => {
    await ctx.get('loader')?.await()
    const agents = ctx.get('agents')
    const sessions = ctx.get('sessions')
    const presets = ctx.get('agentPresets')
    const defaultModel = ctx.get('agentDefaultModel')
    if (!agents || !sessions || !presets || !defaultModel) {
      throw new Error('kitty-headless-runner is missing required DSH services')
    }

    const fallback = defaultModel.currentSelection()
    const selection = {
      ...fallback,
      provider: process.env.KITTY_DSH_PROVIDER || fallback.provider,
      model: process.env.KITTY_DSH_MODEL || fallback.model,
      reasoningEffort: process.env.KITTY_DSH_REASONING_EFFORT || fallback.reasoningEffort || 'high',
    }
    const presetId = process.env.KITTY_DSH_PRESET || presets.defaultId
    const sessionId = SessionId(`session-${randomUUID()}`)
    const { agent } = await agents.create({
      sessionId,
      meta: { cwd: process.cwd(), agentPreset: presetId },
      agentOptions: { provider: selection.provider, model: selection.model },
      setup: async (agentCtx) => {
        installModelSelection(agentCtx, { current: selection, assembled: undefined })
        await presets.mount(agentCtx, presetId)
      },
    })

    await agent.whenIdle()
    const firstSeq = agent.session.seq
    agent.followup(createUserMessage({
      content: [{ type: 'text', text: config.task }],
      source: { kind: 'user' },
    }))
    await agent.whenIdle()
    await sessions.flush(agent.session)
    const outcome = summarize(agent.session.events, firstSeq)
    process.stdout.write(outcome.text + '\n')
    if (outcome.reason?.kind === 'error') {
      process.stderr.write(`kitty-dsh: ${outcome.reason.error.code}: ${outcome.reason.error.message}\n`)
    }
    exit(outcome.reason?.kind === 'completed' ? 0 : 1)
  })().catch((error) => {
    process.stderr.write(`kitty-dsh: ${error instanceof Error ? error.message : String(error)}\n`)
    exit(1)
  })
}
