'use client'

import { useState, type CSSProperties } from 'react'

type Theme = 'cosmic' | 'day' | 'night'

export function OnboardingModal({ onComplete }: { onComplete: (preferences: { name: string; theme: Theme }) => void }) {
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [theme, setTheme] = useState<Theme>('cosmic')

  const finish = () => {
    window.localStorage.setItem('kitty-onboarded', 'true')
    window.localStorage.setItem('kitty-preferred-name', name.trim())
    window.localStorage.setItem('kitty-theme', theme)
    onComplete({ name: name.trim(), theme })
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Welcome to Kitty" style={backdropStyle}>
      <section style={modalStyle}>
        {step === 0 && (
          <>
            <div style={eyebrowStyle}>welcome</div>
            <h2 style={titleStyle}>hey, i&apos;m kitty.</h2>
            <p style={copyStyle}>A local-first companion that keeps the useful thread, tells you when something broke, and stays honest about what it can&apos;t reach.</p>
            <button type="button" onClick={() => setStep(1)} style={buttonStyle}>continue</button>
          </>
        )}
        {step === 1 && (
          <>
            <div style={eyebrowStyle}>make it yours</div>
            <label htmlFor="onboarding-name" style={labelStyle}>what should kitty call you?</label>
            <input id="onboarding-name" value={name} onChange={event => setName(event.target.value)} style={inputStyle} />
            <div style={labelStyle}>pick a theme</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {(['cosmic', 'day', 'night'] as Theme[]).map(candidate => (
                <button
                  key={candidate}
                  type="button"
                  aria-label={`${candidate} theme`}
                  aria-pressed={theme === candidate}
                  onClick={() => setTheme(candidate)}
                  style={{ ...themeButtonStyle, outline: theme === candidate ? '2px solid var(--primary)' : 'none' }}
                >
                  {candidate}
                </button>
              ))}
            </div>
            <button type="button" onClick={() => setStep(2)} style={buttonStyle}>continue</button>
          </>
        )}
        {step === 2 && (
          <>
            <div style={eyebrowStyle}>ready</div>
            <h2 style={titleStyle}>you&apos;re set.</h2>
            <p style={copyStyle}>Start with whatever is actually on your mind. Kitty will keep the useful bits and show clear errors when a service is unavailable.</p>
            <button type="button" onClick={finish} style={buttonStyle}>finish setup</button>
          </>
        )}
      </section>
    </div>
  )
}

const backdropStyle: CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 100, display: 'grid', placeItems: 'center',
  padding: 20, background: 'rgba(10, 8, 7, 0.6)',
}
const modalStyle: CSSProperties = {
  width: 'min(460px, 100%)', display: 'grid', gap: 16, padding: 24,
  background: 'var(--surface)', border: '1.5px solid var(--line)', borderRadius: 16,
  color: 'var(--ink)', boxShadow: 'var(--shadow)',
}
const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--ink-2)' }
const titleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 28, color: 'var(--ink)' }
const copyStyle: CSSProperties = { margin: 0, fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }
const labelStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: 'var(--ink-2)' }
const inputStyle: CSSProperties = { minHeight: 44, padding: '8px 10px', border: '1.5px solid var(--line)', borderRadius: 8, background: 'var(--bg)', color: 'var(--ink)' }
const buttonStyle: CSSProperties = { justifySelf: 'start', minHeight: 44, padding: '8px 16px', border: 'none', borderRadius: 8, background: 'var(--primary)', color: 'var(--on-primary)', fontFamily: 'var(--font-body)', fontWeight: 700, cursor: 'pointer' }
const themeButtonStyle: CSSProperties = { minHeight: 44, padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 8, background: 'var(--bg)', color: 'var(--ink)', cursor: 'pointer' }
