'use client'
import { useState } from 'react'
import { ImageStudio } from '@/components/ImageStudio'
import { ImageGenPanel } from '@/components/ImageGenPanel'
import { useImageStatus } from '@/lib/queries'

export default function StudioView({ isMobile }: { isMobile: boolean }) {
  const [tab, setTab] = useState('gallery')
  const statusQuery = useImageStatus()
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'
  const engines = statusQuery.data?.engines ?? []
  const onlineCount = engines.filter(e => e.available).length

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: pad, paddingBottom: 0 }}>
        <header>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Create</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--ink-2)' }}>
            Generate images with ComfyUI or browse your gallery.
          </p>
          {!statusQuery.isPending && (
            <p style={{ margin: '4px 0 0', fontSize: 11, fontFamily: 'var(--font-mono)', color: onlineCount > 0 ? 'var(--c-green)' : 'var(--c-red)' }}>
              {onlineCount > 0
                ? `${onlineCount}/${engines.length} engine${engines.length === 1 ? '' : 's'} online`
                : 'no image engines online — start ComfyUI or Draw Things'}
            </p>
          )}
        </header>
      </div>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--line)', padding: '12px 24px 0' }}>
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
