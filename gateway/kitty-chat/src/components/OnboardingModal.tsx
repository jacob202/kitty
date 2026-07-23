'use client'

import { useState, type CSSProperties } from 'react'

type Theme = 'cosmic' | 'day' | 'night'

export function OnboardingModal({ onComplete }: { onComplete: (preferences: { name: string; theme: Theme }) => void }) {
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [theme, setTheme] = useState<Theme>('cosmic')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importResult, setImportResult] = useState<{ items: number; message: string } | null>(null)

  const persist = () => {
    window.localStorage.setItem('kitty-onboarded', 'true')
    window.localStorage.setItem('kitty-preferred-name', name.trim())
    window.localStorage.setItem('kitty-theme', theme)
    fetch('/proxy/onboarding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ onboarded: true, preferredName: name.trim(), theme }),
    }).catch(() => {})
    onComplete({ name: name.trim(), theme })
  }

  const handleImport = async () => {
    if (!importFile) return
    setImportBusy(true)
    try {
      const formData = new FormData()
      formData.append('file', importFile)
      const res = await fetch('/proxy/import/chatgpt', { method: 'POST', body: formData })
      if (res.ok) {
        const data = await res.json()
        setImportResult({ items: data.items ?? 0, message: data.message ?? 'Import complete' })
      } else {
        setImportResult({ items: 0, message: 'Import failed — the file may not be a valid ChatGPT export' })
      }
    } catch {
      setImportResult({ items: 0, message: 'Could not reach the gateway to process the import' })
    } finally {
      setImportBusy(false)
    }
  }

  const finish = () => {
    void persist()
  }

  const skipImport = () => {
    void persist()
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
            <div style={eyebrowStyle}>bring your history</div>
            <h2 style={titleStyle}>import past chats</h2>
            <p style={copyStyle}>Got a ChatGPT conversations.json export? Drop it here and Kitty will pull out the useful threads for memory. You can skip this and import later.</p>
            {!importResult && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{
                  border: '1px dashed var(--line)',
                  borderRadius: 6,
                  padding: '8px 14px',
                  fontSize: 12,
                  cursor: 'pointer',
                  color: 'var(--ink-2)',
                }}>
                  {importFile ? importFile.name : 'choose file'}
                  <input type="file" accept=".json" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} style={{ display: 'none' }} />
                </label>
                {importFile && (
                  <button type="button" onClick={() => void handleImport()} disabled={importBusy} style={buttonStyle}>
                    {importBusy ? 'processing…' : 'import'}
                  </button>
                )}
              </div>
            )}
            {importResult && (
              <div style={{ ...copyStyle, padding: '8px 0' }}>
                {importResult.message}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" onClick={() => setStep(3)} style={buttonStyle}>continue</button>
              <button type="button" onClick={skipImport} style={{ ...buttonStyle, background: 'transparent', border: '1px solid var(--line)', color: 'var(--ink-2)' }}>skip</button>
            </div>
          </>
        )}
        {step === 3 && (
          <>
            <div style={eyebrowStyle}>ready</div>
            <h2 style={titleStyle}>you&apos;re set{name ? `, ${name}` : ''}.</h2>
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
