'use client'
import type { CSSProperties } from 'react'
import { usePlugins, useTogglePlugin, useMcpServers, useMcpTools, useGatewayModels } from '@/lib/queries'

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
    note: 'will run as its own service Kitty calls — not vendored into the gateway. not wired yet.',
  },
]

const LANE_COLORS: Record<string, string> = {
  'external escalation': 'var(--c-yellow)',
  'executor lane': 'var(--c-blue)',
  'external / later': 'var(--ink-2)',
}

export function ProviderCenter() {
  const modelsQuery = useGatewayModels()
  const pluginsQuery = usePlugins()
  const togglePlugin = useTogglePlugin()
  const serversQuery = useMcpServers()
  const toolsQuery = useMcpTools()

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
            <button
              onClick={() => togglePlugin.mutate({ name: p.name, enabled: !p.enabled })}
              disabled={togglePlugin.isPending}
              style={{
                ...toggleStyle,
                background: p.enabled ? 'var(--c-green)' : 'var(--surface-2)',
                color: p.enabled ? '#fff' : 'var(--ink-2)',
              }}
            >
              {p.enabled ? 'enabled' : 'disabled'}
            </button>
          </div>
        ))}
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
  letterSpacing: 0,
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
