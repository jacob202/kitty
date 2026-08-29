'use client'
import type { CSSProperties } from 'react'
import { SettingsPanel } from '@/components/SettingsPanel'
import { ProviderCenter } from '@/components/ProviderCenter'

type ThemeMode = 'cosmic' | 'day' | 'night'

export default function SettingsShell({ isMobile, theme, onToggleTheme }: {
  isMobile: boolean
  theme: ThemeMode
  onToggleTheme?: () => void
}) {
  const pad = isMobile ? '20px 16px 124px' : '32px 40px 48px'

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 28, minWidth: 0 }}>
      <header style={{ maxWidth: 720 }}>
        <h1 style={pageTitleStyle}>Settings</h1>
        <p style={pageSubtitleStyle}>Personalize Kitty first. Models, providers, and runtime diagnostics stay available when you need them.</p>
      </header>

      <SettingsPanel theme={theme} onToggleTheme={onToggleTheme ?? (() => {})} />

      <details style={technicalSectionStyle}>
        <summary style={technicalSummaryStyle}>
          <span>
            <strong style={{ display: 'block', color: 'var(--color-text-primary)', fontSize: 16 }}>Provider & runtime details</strong>
            <span style={{ display: 'block', marginTop: 3, color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.45 }}>Routing, provider order, plugins, image engines, MCP, and external execution lanes.</span>
          </span>
        </summary>
        <div style={{ paddingTop: 18 }}><ProviderCenter /></div>
      </details>
    </div>
  )
}

const pageTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 34, lineHeight: 1.15, letterSpacing: '-0.025em', color: 'var(--color-text-primary)' }
const pageSubtitleStyle: CSSProperties = { margin: '8px 0 0', color: 'var(--color-text-secondary)', fontSize: 15, lineHeight: 1.55 }
const technicalSectionStyle: CSSProperties = { maxWidth: 960, minWidth: 0, borderTop: '1px solid var(--color-separator)', paddingTop: 18 }
const technicalSummaryStyle: CSSProperties = { minHeight: 56, display: 'flex', alignItems: 'center', cursor: 'pointer', listStylePosition: 'outside', padding: '4px 2px' }
