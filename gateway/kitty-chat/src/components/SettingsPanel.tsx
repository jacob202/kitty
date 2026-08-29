'use client'
import { useState, useEffect, type CSSProperties } from 'react'
import { useGatewayModels, usePersonality, useUpdatePersonality, useUsageSummary } from '@/lib/queries'
import { useDashboardConfig } from '@/hooks/useDashboardConfig'
import { Button } from '@/components/ui/Button'
import { Palette, RotateCcw, Save } from 'lucide-react'

interface Props { theme: 'cosmic' | 'day' | 'night'; onToggleTheme: () => void }

const DASHBOARD_TILES: { id: string; label: string }[] = [
  { id: 'whats-next', label: "What's Next" }, { id: 'needs-you', label: 'Needs You' },
  { id: 'insight-loop', label: 'Back to You' }, { id: 'deadlines', label: 'Deadlines' },
  { id: 'active-projects', label: 'Active Projects' }, { id: 'what-changed', label: 'What Changed' },
  { id: 'today', label: 'Today' }, { id: 'health', label: 'Health' },
  { id: 'weather', label: 'Weather' }, { id: 'capture', label: 'Capture' },
]

export function SettingsPanel({ theme, onToggleTheme }: Props) {
  const modelsQuery = useGatewayModels()
  const gatewayLive = modelsQuery.data?.fromLiveGateway ?? false
  const { visibleTiles, toggleTile, resetToDefaults } = useDashboardConfig()
  const personality = usePersonality()
  const updatePersonality = useUpdatePersonality()
  const usage = useUsageSummary()
  const [soul, setSoul] = useState('')
  const [prefs, setPrefs] = useState('')

  useEffect(() => {
    if (personality.data) { setSoul(personality.data.soul); setPrefs(personality.data.preferences) }
  }, [personality.data])

  const nextTheme = theme === 'cosmic' ? 'day' : theme === 'day' ? 'night' : 'cosmic'

  return (
    <div aria-label="personal preferences" style={panelStackStyle}>
      <section aria-labelledby="settings-appearance" style={sectionStyle}>
        <div style={sectionIntroStyle}>
          <h2 id="settings-appearance" style={sectionTitleStyle}>Appearance</h2>
          <p style={sectionDescriptionStyle}>Choose how Kitty looks without changing how it works.</p>
        </div>
        <div style={preferenceRowStyle}>
          <div><strong style={rowNameStyle}>Theme</strong><div style={rowNoteStyle}>Currently {theme}.</div></div>
          <Button onClick={onToggleTheme} variant="secondary" size="md" icon={<Palette size={15} />} ariaLabel="Switch theme">Switch to {nextTheme}</Button>
        </div>
      </section>

      <section aria-labelledby="settings-personality" style={sectionStyle}>
        <div style={sectionIntroStyle}>
          <h2 id="settings-personality" style={sectionTitleStyle}>Personality</h2>
          <p style={sectionDescriptionStyle}>Edit the real tone and standing preferences Kitty uses.</p>
        </div>
        {personality.isError && <p role="status" style={errorStyle}>Couldn&apos;t load personality settings.</p>}
        <label style={fieldStyle}><span style={fieldLabelStyle}>Tone description</span><textarea aria-label="tone description" value={soul} onChange={e => setSoul(e.target.value)} rows={4} style={textareaStyle} /></label>
        <label style={fieldStyle}><span style={fieldLabelStyle}>Standing preferences</span><textarea aria-label="standing preferences" value={prefs} onChange={e => setPrefs(e.target.value)} rows={4} style={textareaStyle} /></label>
        {updatePersonality.isError && <p role="status" style={errorStyle}>Couldn&apos;t save personality settings.</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button onClick={() => updatePersonality.mutate({ soul, preferences: prefs })} disabled={updatePersonality.isPending} variant="primary" size="md" icon={<Save size={15} />}>save personality</Button>
        </div>
      </section>

      <section aria-labelledby="settings-home" style={sectionStyle}>
        <div style={sectionIntroStyle}>
          <h2 id="settings-home" style={sectionTitleStyle}>Home</h2>
          <p style={sectionDescriptionStyle}>Choose which real dashboard sections stay visible.</p>
        </div>
        <div style={tileGridStyle}>
          {DASHBOARD_TILES.map(tile => (
            <label key={tile.id} style={tileRowStyle}>
              <span style={rowNameStyle}>{tile.label}</span>
              <input type="checkbox" checked={visibleTiles[tile.id] ?? true} onChange={() => toggleTile(tile.id)} style={checkboxStyle} />
            </label>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}><Button onClick={resetToDefaults} variant="ghost" size="md" icon={<RotateCcw size={15} />}>reset to defaults</Button></div>
      </section>

      <section aria-labelledby="settings-models" style={sectionStyle}>
        <div style={sectionIntroStyle}>
          <h2 id="settings-models" style={sectionTitleStyle}>Models & usage</h2>
          <p style={sectionDescriptionStyle}>A readable summary of what Kitty can route to and what recent usage looks like.</p>
        </div>
        <div style={summaryRowStyle}>
          <div><strong style={rowNameStyle}>Model access</strong><div style={rowNoteStyle}>{gatewayLive ? 'Gateway connected' : 'Gateway unavailable'}</div></div>
          <span style={statusPillStyle(gatewayLive)}>{gatewayLive ? 'Connected' : 'Offline'}</span>
        </div>
        {(modelsQuery.data?.models ?? []).length > 0 ? (
          <div style={modelNamesStyle}>{modelsQuery.data?.models.map(model => <span key={model.id} style={modelChipStyle}>{model.name}</span>)}</div>
        ) : <p style={rowNoteStyle}>No model list available.</p>}
        {usage.data ? (
          <div style={usageGridStyle}>
            <div aria-label={`${usage.data.totals.calls} calls`}><strong style={metricStyle}>{usage.data.totals.calls}</strong><span style={metricLabelStyle}>calls</span></div>
            <div><strong style={metricStyle}>{usage.data.totals.tokens.toLocaleString()}</strong><span style={metricLabelStyle}>tokens</span></div>
            <div><strong style={metricStyle}>${usage.data.estimated_cost.cad.toFixed(2)}</strong><span style={metricLabelStyle}>CAD estimated</span></div>
          </div>
        ) : <p style={rowNoteStyle}>No usage data yet.</p>}
        {usage.data?.cost_estimate_disclaimer && <p style={disclaimerStyle}>{usage.data.cost_estimate_disclaimer}</p>}

        <details style={detailsStyle}>
          <summary style={detailsSummaryStyle}>Technical details</summary>
          <div style={technicalGridStyle}>
            <div><span style={technicalLabelStyle}>Gateway endpoint</span><code style={codeStyle}>127.0.0.1:8000 via /proxy</code></div>
            <div><span style={technicalLabelStyle}>Gateway state</span><span>{gatewayLive ? 'live' : `offline${modelsQuery.data?.error ? ` — ${modelsQuery.data.error}` : ''}`}</span></div>
            {(modelsQuery.data?.models ?? []).map(model => <div key={model.id}><span style={technicalLabelStyle}>{model.name}</span><code style={codeStyle}>{model.id}</code></div>)}
            <div><span style={technicalLabelStyle}>Phone access</span><span>The UI is loopback by default. For tailnet development use <code style={codeStyle}>npm run dev:tailnet</code> or <code style={codeStyle}>make ui-tailnet</code>; the Gateway remains loopback-only.</span></div>
          </div>
        </details>
      </section>
    </div>
  )
}

function statusPillStyle(ok: boolean): CSSProperties { return { borderRadius: 999, padding: '5px 10px', fontSize: 12, fontWeight: 650, color: ok ? 'var(--c-green)' : 'var(--c-red)', background: 'var(--surface-2)', flexShrink: 0 } }
const panelStackStyle: CSSProperties = { display: 'grid', gap: 30, alignContent: 'start', minWidth: 0, maxWidth: 960 }
const sectionStyle: CSSProperties = { display: 'grid', gap: 14, minWidth: 0, paddingTop: 20, borderTop: '1px solid var(--line)' }
const sectionIntroStyle: CSSProperties = { maxWidth: 680 }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 21, fontWeight: 700, color: 'var(--ink)' }
const sectionDescriptionStyle: CSSProperties = { margin: '4px 0 0', fontSize: 13, lineHeight: 1.5, color: 'var(--ink-2)' }
const preferenceRowStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, minWidth: 0, flexWrap: 'wrap' }
const summaryRowStyle: CSSProperties = { ...preferenceRowStyle, padding: '2px 0' }
const rowNameStyle: CSSProperties = { fontSize: 14, fontWeight: 650, color: 'var(--ink)' }
const rowNoteStyle: CSSProperties = { margin: 0, marginTop: 2, fontSize: 12, lineHeight: 1.45, color: 'var(--ink-2)' }
const fieldStyle: CSSProperties = { display: 'grid', gap: 6, minWidth: 0 }
const fieldLabelStyle: CSSProperties = { fontSize: 13, fontWeight: 650, color: 'var(--ink)' }
const textareaStyle: CSSProperties = { width: '100%', minWidth: 0, fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: 1.5, padding: '11px 12px', borderRadius: 'var(--r-control)', border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)', resize: 'vertical' }
const tileGridStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0 24px', minWidth: 0 }
const tileRowStyle: CSSProperties = { minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, borderBottom: '1px solid var(--line)', cursor: 'pointer' }
const checkboxStyle: CSSProperties = { width: 20, height: 20, accentColor: 'var(--primary)', cursor: 'pointer', flexShrink: 0 }
const modelNamesStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap' }
const modelChipStyle: CSSProperties = { padding: '6px 10px', borderRadius: 999, background: 'var(--surface-2)', color: 'var(--ink)', fontSize: 12, border: '1px solid var(--line)' }
const usageGridStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12, paddingTop: 4 }
const metricStyle: CSSProperties = { display: 'block', fontSize: 20, fontFamily: 'var(--font-display)', color: 'var(--ink)' }
const metricLabelStyle: CSSProperties = { display: 'block', marginTop: 2, fontSize: 11, color: 'var(--ink-2)' }
const disclaimerStyle: CSSProperties = { margin: 0, fontSize: 11, lineHeight: 1.45, color: 'var(--ink-2)' }
const detailsStyle: CSSProperties = { marginTop: 4, borderTop: '1px solid var(--line)', paddingTop: 8 }
const detailsSummaryStyle: CSSProperties = { minHeight: 44, display: 'inline-flex', alignItems: 'center', cursor: 'pointer', color: 'var(--ink)', fontSize: 13, fontWeight: 650 }
const technicalGridStyle: CSSProperties = { marginTop: 8, display: 'grid', gap: 10, padding: '12px 14px', background: 'var(--surface-2)', borderRadius: 'var(--r-control)', color: 'var(--ink-2)', fontSize: 12, lineHeight: 1.5, overflowWrap: 'anywhere' }
const technicalLabelStyle: CSSProperties = { display: 'block', marginBottom: 2, color: 'var(--ink)', fontWeight: 650 }
const codeStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink)', overflowWrap: 'anywhere' }
const errorStyle: CSSProperties = { margin: 0, color: 'var(--c-red)', fontSize: 13 }
