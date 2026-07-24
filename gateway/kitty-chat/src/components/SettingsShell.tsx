'use client'
import { SettingsPanel } from '@/components/SettingsPanel'
import { ProviderCenter } from '@/components/ProviderCenter'
import { useState } from 'react'

type ThemeMode = 'cosmic' | 'day' | 'night'

export default function SettingsShell({ isMobile, theme, onToggleTheme }: {
  isMobile: boolean
  theme: ThemeMode
  onToggleTheme?: () => void
}) {
  const [tab, setTab] = useState('general')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'providers', label: 'Providers' },
    { id: 'skills', label: 'Skills' },
    { id: 'advanced', label: 'Advanced' },
  ]

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--line)', paddingBottom: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px', border: 'none',
              background: tab === t.id ? 'var(--ginger-fade)' : 'transparent',
              color: tab === t.id ? 'var(--cat-ginger)' : 'var(--ink-2)',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid var(--cat-ginger)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && <SettingsPanel theme={theme} onToggleTheme={onToggleTheme!} />}
      {tab === 'providers' && <ProviderCenter />}
      {tab === 'skills' && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.8 }}>
          <p><strong>Tutor</strong> — learn, quiz, master</p>
          <p><strong>Agents</strong> — spawn, watch, stop autonomous workers</p>
          <p><strong>Tools</strong> — monitors, image gen, loops, insights, prompts</p>
          <p style={{ marginTop: 12, fontSize: 11 }}>These features are unrouted until they earn daily use. Launch from here or via command palette.</p>
        </div>
      )}
      {tab === 'advanced' && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink-2)' }}>
          <p>Theme: {theme}</p>
          <p>Advanced settings will appear here as features mature.</p>
        </div>
      )}
    </div>
  )
}
