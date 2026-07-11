'use client'
import type { CSSProperties } from 'react'
import { useGatewayModels } from '@/lib/queries'
import { useDashboardConfig } from '@/hooks/useDashboardConfig'

interface Props {
  theme: 'cosmic' | 'day' | 'night'
  onToggleTheme: () => void
}

const DASHBOARD_TILES: { id: string; label: string }[] = [
  { id: 'whats-next', label: "What's Next" },
  { id: 'needs-you', label: 'Needs You' },
  { id: 'deadlines', label: 'Deadlines' },
  { id: 'active-projects', label: 'Active Projects' },
  { id: 'what-changed', label: 'What Changed' },
  { id: 'today', label: 'Today' },
  { id: 'health', label: 'Health' },
  { id: 'capture', label: 'Capture' },
]

export function SettingsPanel({ theme, onToggleTheme }: Props) {
  const modelsQuery = useGatewayModels()
  const gatewayLive = modelsQuery.data?.fromLiveGateway ?? false
  const { visibleTiles, toggleTile, resetToDefaults } = useDashboardConfig()

  return (
    <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
      <header>
        <h2 style={titleStyle}>settings</h2>
        <p style={subtitleStyle}>the few knobs that turn from here.</p>
      </header>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>appearance</div>
        <div style={rowStyle}>
          <span style={rowNameStyle}>theme</span>
          <button onClick={onToggleTheme} style={buttonStyle}>
            {theme === 'cosmic' ? '✦ cosmic — switch to day' : theme === 'day' ? '☀ day — switch to night' : '☾ night — switch to cosmic'}
          </button>
        </div>
      </div>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>dashboard tiles</div>
        {DASHBOARD_TILES.map((tile) => (
          <label key={tile.id} style={{ ...rowStyle, cursor: 'pointer' }}>
            <span style={rowNameStyle}>{tile.label}</span>
            <input
              type="checkbox"
              checked={visibleTiles[tile.id] ?? true}
              onChange={() => toggleTile(tile.id)}
              style={checkboxStyle}
            />
          </label>
        ))}
        <div style={resetRowStyle}>
          <button onClick={resetToDefaults} style={buttonStyle}>
            reset to defaults
          </button>
        </div>
      </div>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>gateway</div>
        <div style={rowStyle}>
          <span style={rowNameStyle}>endpoint</span>
          <span style={monoValueStyle}>127.0.0.1:8000 via /proxy</span>
        </div>
        <div style={rowStyle}>
          <span style={rowNameStyle}>status</span>
          <span style={{ ...monoValueStyle, color: gatewayLive ? 'var(--c-green)' : 'var(--c-red)' }}>
            {gatewayLive ? '● live' : `● offline${modelsQuery.data?.error ? ` — ${modelsQuery.data.error}` : ''}`}
          </span>
        </div>
      </div>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>phone access — tailscale</div>
        <p style={noteStyle}>
          the dev server binds loopback by default, so the phone can&apos;t see it. to reach kitty
          from the phone over the tailnet, start the UI with{' '}
          <code style={codeStyle}>npm run dev:tailnet</code> (or <code style={codeStyle}>make ui-tailnet</code>)
          and open <code style={codeStyle}>http://&lt;mac-tailscale-name&gt;:4000</code>. the gateway
          itself stays loopback-only — the UI proxies to it server-side.
        </p>
      </div>
    </div>
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
  gap: 8,
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'lowercase',
  color: 'var(--ink-2)',
  paddingBottom: 6,
  borderBottom: '1px solid var(--line)',
}

const rowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '4px 0',
}

const rowNameStyle: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--ink)',
}

const monoValueStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  textAlign: 'right',
}

const buttonStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
  padding: '6px 14px',
  border: '1.5px solid var(--line)',
  borderRadius: 10,
  background: 'var(--surface-2)',
  color: 'var(--ink)',
  cursor: 'pointer',
}

const checkboxStyle: CSSProperties = {
  width: 16,
  height: 16,
  accentColor: 'var(--primary)',
  cursor: 'pointer',
}

const resetRowStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  paddingTop: 6,
  marginTop: 2,
  borderTop: '1px solid var(--line)',
}

const noteStyle: CSSProperties = {
  fontSize: 13,
  lineHeight: 1.6,
  color: 'var(--ink)',
}

const codeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  background: 'var(--surface-2)',
  padding: '1px 5px',
  borderRadius: 4,
}
