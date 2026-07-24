'use client'
import { useState } from 'react'
import { ImageStudio } from '@/components/ImageStudio'
import { ImageGenPanel } from '@/components/ImageGenPanel'

export default function StudioView({ isMobile }: { isMobile: boolean }) {
  const [tab, setTab] = useState('gallery')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--line)', padding: '8px 24px 0' }}>
        {[
          { id: 'gallery', label: 'Gallery' },
          { id: 'generate', label: 'Generate' },
        ].map((t) => (
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
      <div style={{ padding: pad, flex: 1, overflow: 'auto' }}>
        {tab === 'gallery' ? <ImageStudio /> : <ImageGenPanel />}
      </div>
    </div>
  )
}
