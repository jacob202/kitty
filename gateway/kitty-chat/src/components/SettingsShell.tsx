'use client'
import { SettingsPanel } from '@/components/SettingsPanel'
import { ProviderCenter } from '@/components/ProviderCenter'

type ThemeMode = 'cosmic' | 'day' | 'night'

export default function SettingsShell({ isMobile, theme, onToggleTheme }: {
  isMobile: boolean
  theme: ThemeMode
  onToggleTheme?: () => void
}) {
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Settings</h1>
        <p style={{ margin: '4px 0 0', color: 'var(--ink-2)' }}>
          Configure providers, appearance, and connected services.
        </p>
      </header>

      <SettingsPanel theme={theme} onToggleTheme={onToggleTheme!} />

      <section>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: '0 0 12px' }}>
          Providers
        </h2>
        <ProviderCenter />
      </section>

      <section style={{
        background: 'var(--surface)',
        border: '1.5px solid var(--line)',
        borderRadius: 14,
        padding: 18,
        display: 'grid',
        gap: 10,
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'lowercase',
          color: 'var(--ink-2)',
        }}>
          journal · tutor · terminal · agents
        </span>
        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: 13,
          color: 'var(--ink)',
          lineHeight: 1.6,
          margin: 0,
        }}>
          Journal, Tutor, Terminal, and Agents are available from the command
          palette (<kbd style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            padding: '1px 6px',
            border: '1px solid var(--line)',
            borderRadius: 4,
          }}>⌘K</kbd>), the sidebar rail, or the mobile More menu.
          They earn a top-level tab when usage data justifies it.
        </p>
      </section>

      <section style={{
        background: 'var(--surface)',
        border: '1.5px solid var(--line)',
        borderRadius: 14,
        padding: 18,
        display: 'grid',
        gap: 10,
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'lowercase',
          color: 'var(--ink-2)',
        }}>
          about
        </span>
        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: 13,
          color: 'var(--ink)',
          lineHeight: 1.6,
          margin: 0,
        }}>
          Theme: <strong>{theme}</strong>. Kitty is a local-first personal AI
          companion. The gateway runs on <code style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            padding: '1px 5px',
            borderRadius: 4,
            background: 'var(--surface-2)',
          }}>127.0.0.1:8000</code>, routing
          through LiteLLM on port 8001. Model selection, provider configuration,
          and personality tuning are available above.
        </p>
      </section>
    </div>
  )
}
