'use client'
import { useEffect, useState, type CSSProperties } from 'react'
import { useGatewayModels, usePersonality, useUpdatePersonality, useUsageSummary } from '@/lib/queries'

interface Props {
  theme: 'cosmic' | 'day' | 'night'
  onToggleTheme: () => void
}

const NOT_WIRED = [
  { name: 'gateway secret & env', where: '.env in the repo root' },
]

export function SettingsPanel({ theme, onToggleTheme }: Props) {
  const modelsQuery = useGatewayModels()
  const personalityQuery = usePersonality()
  const updatePersonality = useUpdatePersonality()
  const usageQuery = useUsageSummary()
  const gatewayLive = modelsQuery.data?.fromLiveGateway ?? false
  const [soul, setSoul] = useState('')
  const [preferences, setPreferences] = useState('')
  const [personalityDirty, setPersonalityDirty] = useState(false)

  useEffect(() => {
    if (!personalityQuery.data || personalityDirty) return
    setSoul(personalityQuery.data.soul)
    setPreferences(personalityQuery.data.preferences)
  }, [personalityQuery.data, personalityDirty])

  useEffect(() => {
    if (updatePersonality.isSuccess) setPersonalityDirty(false)
  }, [updatePersonality.isSuccess])

  const voicePreview = soul
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .slice(0, 4)
    .join(' ')

  const savePersonality = () => {
    updatePersonality.mutate({ soul, preferences })
  }

  return (
    <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
      <header>
        <h2 style={titleStyle}>settings</h2>
        <p style={subtitleStyle}>the few knobs that turn from here, and where the rest live.</p>
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
        <div style={sectionLabelStyle}>personality</div>
        {personalityQuery.isPending ? (
          <p style={noteStyle}>loading personality files…</p>
        ) : personalityQuery.isError ? (
          <p role="alert" style={errorStyle}>
            couldn&apos;t read personality files — {personalityQuery.error instanceof Error ? personalityQuery.error.message : 'gateway error'}
          </p>
        ) : (
          <>
            <label style={fieldLabelStyle} htmlFor="personality-soul">tone description</label>
            <textarea
              id="personality-soul"
              aria-label="tone description"
              value={soul}
              onChange={event => { setPersonalityDirty(true); setSoul(event.target.value) }}
              style={textareaStyle}
            />
            <label style={fieldLabelStyle} htmlFor="personality-preferences">standing preferences</label>
            <textarea
              id="personality-preferences"
              aria-label="standing preferences"
              value={preferences}
              onChange={event => { setPersonalityDirty(true); setPreferences(event.target.value) }}
              style={textareaStyle}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" onClick={savePersonality} disabled={updatePersonality.isPending} style={buttonStyle}>
                {updatePersonality.isPending ? 'saving…' : 'save personality'}
              </button>
              {updatePersonality.isError && (
                <span role="alert" style={errorStyle}>
                  save failed — {updatePersonality.error instanceof Error ? updatePersonality.error.message : 'gateway error'}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>voice preview</div>
        <p style={noteStyle}>{voicePreview || 'personality text has no visible preview yet.'}</p>
      </div>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>models and routing</div>
        {modelsQuery.isPending ? (
          <p style={noteStyle}>checking configured models…</p>
        ) : modelsQuery.isError ? (
          <p role="alert" style={errorStyle}>
            couldn&apos;t read configured models — {modelsQuery.error instanceof Error ? modelsQuery.error.message : 'gateway error'}
          </p>
        ) : (
          <>
            <div style={{ ...rowStyle, flexWrap: 'wrap', justifyContent: 'flex-start' }}>
              {(modelsQuery.data?.models ?? []).map(model => (
                <span key={model.id} style={chipStyle}>{model.name}</span>
              ))}
            </div>
            <p style={noteStyle}>
              {gatewayLive ? 'provider endpoint reachable.' : `provider endpoint unreachable${modelsQuery.data?.error ? ` — ${modelsQuery.data.error}` : ''}`}
              {' '}Reasoning and explicit “best model” requests route to kitty-sonnet; everything else uses the default route.
            </p>
          </>
        )}
      </div>

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>usage</div>
        {usageQuery.isPending ? (
          <p style={noteStyle}>loading recorded usage…</p>
        ) : usageQuery.isError ? (
          <p role="alert" style={errorStyle}>
            couldn&apos;t read usage — {usageQuery.error instanceof Error ? usageQuery.error.message : 'gateway error'}
          </p>
        ) : usageQuery.data ? (
          <p style={noteStyle}>
            {usageQuery.data.totals.calls} logged calls · {usageQuery.data.totals.tokens.toLocaleString()} tokens · estimated ${usageQuery.data.estimated_cost.cad.toFixed(4)} CAD. {usageQuery.data.cost_estimate_disclaimer}
          </p>
        ) : null}
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

      <div style={cardStyle}>
        <div style={sectionLabelStyle}>not wired here yet — lives on disk</div>
        {NOT_WIRED.map(item => (
          <div key={item.name} style={rowStyle}>
            <span style={rowNameStyle}>{item.name}</span>
            <span style={monoValueStyle}>{item.where}</span>
          </div>
        ))}
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

const fieldLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  color: 'var(--ink-2)',
}

const textareaStyle: CSSProperties = {
  width: '100%',
  minHeight: 112,
  resize: 'vertical',
  padding: 10,
  border: '1.5px solid var(--line)',
  borderRadius: 8,
  background: 'var(--bg)',
  color: 'var(--ink)',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  lineHeight: 1.5,
}

const errorStyle: CSSProperties = {
  color: 'var(--c-red)',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
}

const chipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '3px 8px',
  border: '1px solid var(--line)',
  borderRadius: 999,
  color: 'var(--ink-2)',
}
