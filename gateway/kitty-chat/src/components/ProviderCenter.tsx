'use client'
import type { CSSProperties } from 'react'
import { usePlugins, useTogglePlugin, useMcpServers, useMcpTools, useGatewayModels, useModelRouting, useProviders, useSaveProviders, useImageStatus } from '@/lib/queries'
import { Button } from '@/components/ui/Button'
import { RefreshCw, ChevronUp, ChevronDown } from 'lucide-react'

// Honest lanes — these are how Jacob actually reaches each thing today.
// A subscription in a browser is not an API; don't dress it up as one.
const EXTERNAL_LANES: Array<{
  name: string
  lane: 'external escalation' | 'executor lane' | 'external / later'
  note: string
}> = [
  {
    name: 'ChatGPT',
    lane: 'external escalation',
    note: 'browser subscription — no API wired. Kitty can prep the prompt; you paste it.',
  },
  {
    name: 'Gemini',
    lane: 'external escalation',
    note: 'browser subscription — no API wired. escalate by hand when you need it.',
  },
  {
    name: 'Claude',
    lane: 'external escalation',
    note: 'browser subscription — no API wired. same deal: prep here, run there.',
  },
  {
    name: 'Codex CLI',
    lane: 'executor lane',
    note: 'runs in the Mac terminal. hand it an executor-ready packet from docs/packets/.',
  },
  {
    name: 'Claude Code',
    lane: 'executor lane',
    note: 'runs in the Mac terminal. the other packet executor.',
  },
  {
    name: 'ComfyUI',
    lane: 'external / later',
    note: 'local image engine Kitty calls through the gateway. health is shown below; the renderer remains external.',
  },
  {
    name: 'Draw Things',
    lane: 'external / later',
    note: 'A1111-compatible local image engine. Kitty can route Image Lab requests here when its API server is enabled.',
  },
]

const LANE_COLORS: Record<string, string> = {
  'external escalation': 'var(--c-yellow)',
  'executor lane': 'var(--c-blue)',
  'external / later': 'var(--ink-2)',
}

export function ProviderCenter() {
  const modelsQuery = useGatewayModels()
  const routingQuery = useModelRouting()
  const pluginsQuery = usePlugins()
  const togglePlugin = useTogglePlugin()
  const serversQuery = useMcpServers()
  const toolsQuery = useMcpTools()
  const imageStatusQuery = useImageStatus()

  const modelsLive = modelsQuery.data?.fromLiveGateway ?? false
  const models = modelsQuery.data?.models ?? []

  return (
    <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
      <header>
        <h2 style={titleStyle}>providers</h2>
        <p style={subtitleStyle}>
          what kitty can actually call, what needs your hands, and what&apos;s honestly not wired.
        </p>
      </header>

      {/* ── model routing ── */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={sectionLabelStyle}>model routing — litellm via gateway</span>
          <span style={{ flex: 1 }} />
          <StatusDot ok={modelsLive} okLabel="live" badLabel="gateway offline" />
        </div>
        {modelsLive ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {models.map(m => (
              <span key={m.id} style={{ ...chipStyle, borderColor: m.color, color: 'var(--ink)' }}>
                {m.name}
              </span>
            ))}
          </div>
        ) : (
          <p style={mutedStyle}>
            {modelsQuery.data?.error ?? 'gateway not reachable'} — the list below is a fallback,
            not what&apos;s actually routable right now.
          </p>
        )}
      </div>

      <ProviderChain />

      {/* ── who each alias actually calls ── */}
      <div style={cardStyle}>
        <div style={sectionLabelStyle}>
          where each model name goes — read from gateway/litellm_config.yaml
        </div>
        <p style={mutedStyle}>
          the kitty-* names are roles, not models. this is the provider behind each one.
        </p>

        {routingQuery.isLoading && <p style={mutedStyle}>reading routing config…</p>}
        {routingQuery.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            couldn&apos;t read model routing —{' '}
            {routingQuery.error instanceof Error ? routingQuery.error.message : 'gateway error'}
          </p>
        )}
        {routingQuery.data && !routingQuery.data.readable && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>{routingQuery.data.error}</p>
        )}

        {(routingQuery.data?.routes ?? []).map(route => (
          <div key={route.alias} style={rowStyle}>
            <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
              <span style={rowNameStyle}>{route.alias}</span>
              <span style={rowNoteStyle}>
                {route.provider} → {route.upstream_model}
                {route.fallbacks.length > 0 && ` · falls back to ${route.fallbacks.join(', ')}`}
              </span>
            </div>
            <span style={{ marginLeft: 'auto' }}>
              {route.key.env_var ? (
                <StatusDot
                  ok={route.key.present}
                  okLabel={`${route.key.env_var} set`}
                  badLabel={`${route.key.env_var} missing`}
                />
              ) : (
                <span style={metaStyle}>{route.key.note}</span>
              )}
            </span>
          </div>
        ))}

        {(routingQuery.data?.warnings ?? []).map(warning => (
          <p key={warning} style={{ ...mutedStyle, color: 'var(--c-yellow)' }}>⚠ {warning}</p>
        ))}

        {routingQuery.data?.readable && (
          <p style={mutedStyle}>
            repointing an alias at a different model still means editing{' '}
            {routingQuery.data.config_path} and restarting litellm. changing which
            provider answers is the call order above — that one is live.
          </p>
        )}
      </div>

      {/* ── plugins ── */}
      <div style={cardStyle}>
        <div style={sectionLabelStyle}>plugins</div>
        {pluginsQuery.isLoading && <p style={mutedStyle}>loading plugins…</p>}
        {pluginsQuery.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            couldn&apos;t read plugins —{' '}
            {pluginsQuery.error instanceof Error ? pluginsQuery.error.message : 'gateway error'}
          </p>
        )}
        {pluginsQuery.data?.length === 0 && <p style={mutedStyle}>no plugins registered.</p>}
        {(pluginsQuery.data ?? []).map(p => (
          <div key={p.name} style={rowStyle}>
            <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
              <span style={rowNameStyle}>{p.name}</span>
              {p.description && <span style={rowNoteStyle}>{p.description}</span>}
            </div>
            <Button
              onClick={() => togglePlugin.mutate({ name: p.name, enabled: !p.enabled })}
              disabled={togglePlugin.isPending}
              variant={p.enabled ? 'primary' : 'secondary'}
              size="sm"
            >
              {p.enabled ? 'enabled' : 'disabled'}
            </Button>
          </div>
        ))}
      </div>

      {/* ── image engines ── */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={sectionLabelStyle}>image engines — gateway routed</span>
          <span style={{ flex: 1 }} />
          <Button
            onClick={() => void imageStatusQuery.refetch()}
            disabled={imageStatusQuery.isFetching}
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={12} />}
          >
            {imageStatusQuery.isFetching ? 'checking…' : 'refresh'}
          </Button>
        </div>
        {imageStatusQuery.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            couldn&apos;t read image engine health — gateway error
          </p>
        )}
        {(imageStatusQuery.data?.engines ?? []).map(engine => (
          <div key={engine.name} style={rowStyle}>
            <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
              <span style={rowNameStyle}>{engine.label}</span>
              <span style={rowNoteStyle}>{engine.name}</span>
            </div>
            <StatusDot ok={engine.available} okLabel="online" badLabel="offline" />
          </div>
        ))}
        {imageStatusQuery.data?.engines?.length === 0 && (
          <p style={mutedStyle}>no image engine status returned by the gateway.</p>
        )}
      </div>

      {/* ── mcp ── */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={sectionLabelStyle}>mcp servers</span>
          <span style={{ flex: 1 }} />
          {toolsQuery.data && <span style={metaStyle}>{toolsQuery.data.length} tools exposed</span>}
        </div>
        {serversQuery.isLoading && <p style={mutedStyle}>loading servers…</p>}
        {serversQuery.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            couldn&apos;t read MCP servers —{' '}
            {serversQuery.error instanceof Error ? serversQuery.error.message : 'gateway error'}
          </p>
        )}
        {serversQuery.data?.length === 0 && (
          <p style={mutedStyle}>no MCP servers configured — .mcp.json is empty or absent.</p>
        )}
        {(serversQuery.data ?? []).map((s, i) => (
          <div key={`${s.name}-${i}`} style={rowStyle}>
            <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
              <span style={rowNameStyle}>{s.name}</span>
              {typeof s.command === 'string' && s.command && (
                <span style={rowNoteStyle}>{s.command}</span>
              )}
            </div>
            <span style={{ ...chipStyle, marginLeft: 'auto' }}>
              {typeof s.source === 'string' ? s.source : 'plugin'}
            </span>
          </div>
        ))}
      </div>

      {/* ── external lanes ── */}
      <div style={cardStyle}>
        <div style={sectionLabelStyle}>external lanes — not APIs, and not pretending to be</div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: 10,
          }}
        >
          {EXTERNAL_LANES.map(lane => (
            <div key={lane.name} style={laneCardStyle}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={rowNameStyle}>{lane.name}</span>
                <span style={{ flex: 1 }} />
                <span style={{ ...laneChipStyle, color: LANE_COLORS[lane.lane] }}>{lane.lane}</span>
              </div>
              <p style={rowNoteStyle}>{lane.note}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/** Reorder and disable the fallback chain in place — the switch that used to
 *  mean editing PROVIDER_FALLBACK_ORDER in Python and restarting. */
function ProviderChain() {
  const chainQuery = useProviders()
  const save = useSaveProviders()

  const providers = chainQuery.data?.providers ?? []
  const order = chainQuery.data?.order ?? []

  function move(name: string, delta: number) {
    const next = [...order]
    const from = next.indexOf(name)
    const to = from + delta
    if (from < 0 || to < 0 || to >= next.length) return
    ;[next[from], next[to]] = [next[to], next[from]]
    save.mutate({ order: next, disabled: providers.filter(p => p.disabled).map(p => p.name) })
  }

  function toggle(name: string, disabled: boolean) {
    const nextDisabled = disabled
      ? [...providers.filter(p => p.disabled).map(p => p.name), name]
      : providers.filter(p => p.disabled && p.name !== name).map(p => p.name)
    save.mutate({ order, disabled: nextDisabled })
  }

  return (
    <div style={cardStyle}>
      <div style={sectionLabelStyle}>call order — first one that answers wins</div>
      <p style={mutedStyle}>
        kitty tries litellm first, then walks this list. reordering takes effect on the
        next call — no restart.
      </p>

      {chainQuery.isLoading && <p style={mutedStyle}>reading provider chain…</p>}
      {chainQuery.isError && (
        <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
          couldn&apos;t read the provider chain —{' '}
          {chainQuery.error instanceof Error ? chainQuery.error.message : 'gateway error'}
        </p>
      )}
      {save.isError && (
        <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
          couldn&apos;t save —{' '}
          {save.error instanceof Error ? save.error.message : 'gateway rejected the change'}
        </p>
      )}

      {providers.map(provider => (
        <div key={provider.name} style={rowStyle}>
          <span style={{ ...metaStyle, width: 18, flexShrink: 0 }}>
            {provider.position === null ? '—' : provider.position + 1}
          </span>
          <div style={{ display: 'grid', gap: 2, minWidth: 0 }}>
            <span style={{ ...rowNameStyle, opacity: provider.disabled ? 0.45 : 1 }}>
              {provider.name}
            </span>
            <span style={rowNoteStyle}>
              {provider.model ?? provider.model_env ?? provider.base_url}
              {!provider.requires_key && ' · no key needed'}
            </span>
          </div>
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <StatusDot
              ok={provider.configured}
              okLabel="ready"
              badLabel={provider.api_key_env[0] ? `${provider.api_key_env[0]} missing` : 'not configured'}
            />
            <Button
              onClick={() => move(provider.name, -1)}
              disabled={save.isPending || provider.disabled || provider.position === 0}
              variant="ghost"
              size="sm"
              icon={<ChevronUp size={12} />}
              ariaLabel={`Move ${provider.name} up`}
            >{''}</Button>
            <Button
              onClick={() => move(provider.name, 1)}
              disabled={save.isPending || provider.disabled || provider.position === order.length - 1}
              variant="ghost"
              size="sm"
              icon={<ChevronDown size={12} />}
              ariaLabel={`Move ${provider.name} down`}
            >{''}</Button>
            <Button
              onClick={() => toggle(provider.name, !provider.disabled)}
              disabled={save.isPending}
              variant={provider.disabled ? 'secondary' : 'primary'}
              size="sm"
              ariaLabel={`${provider.disabled ? 'Enable' : 'Disable'} ${provider.name}`}
            >
              {provider.disabled ? 'off' : 'on'}
            </Button>
          </span>
        </div>
      ))}

      {(chainQuery.data?.warnings ?? []).map(warning => (
        <p key={warning} style={{ ...mutedStyle, color: 'var(--c-yellow)' }}>⚠ {warning}</p>
      ))}
    </div>
  )
}

function StatusDot({ ok, okLabel, badLabel }: { ok: boolean; okLabel: string; badLabel: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, ...metaStyle }}>
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: ok ? 'var(--c-green)' : 'var(--c-red)',
          display: 'inline-block',
        }}
      />
      {ok ? okLabel : badLabel}
    </span>
  )
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 800,
  fontSize: 28,
  letterSpacing: '-0.02em',
  color: 'var(--ink)',
}

const subtitleStyle: CSSProperties = {
  fontSize: 13,
  color: 'var(--ink-2)',
  marginTop: 2,
}

const cardStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  borderRadius: 14,
  padding: 18,
  display: 'grid',
  gap: 10,
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'lowercase',
  color: 'var(--ink-2)',
}

const rowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '8px 0',
  borderBottom: '1px solid var(--line)',
}

const rowNameStyle: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--ink)',
}

const rowNoteStyle: CSSProperties = {
  fontSize: 12,
  color: 'var(--ink-2)',
  lineHeight: 1.5,
}

const toggleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.06em',
  padding: '4px 12px',
  border: '1.5px solid var(--line)',
  borderRadius: 999,
  cursor: 'pointer',
  flexShrink: 0,
  marginLeft: 'auto',
}

const refreshStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '3px 8px',
  color: 'var(--ink-2)',
  background: 'transparent',
  border: '1px solid var(--line)',
  borderRadius: 4,
  cursor: 'pointer',
}

const chipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.06em',
  padding: '2px 8px',
  border: '1px solid var(--line)',
  borderRadius: 999,
  color: 'var(--ink-2)',
  flexShrink: 0,
}

const laneCardStyle: CSSProperties = {
  background: 'var(--bg)',
  border: '1.5px solid var(--line)',
  borderRadius: 10,
  padding: '10px 12px',
  display: 'grid',
  gap: 6,
}

const laneChipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  whiteSpace: 'nowrap',
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const mutedStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--ink-2)',
  lineHeight: 1.6,
}
