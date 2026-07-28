'use client'
import { useSearchParams } from 'next/navigation'
import { DocumentsPanel } from '@/components/DocumentsPanel'

export default function LibraryView({ isMobile }: { isMobile: boolean }) {
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <header>
        <h1 style={{
          margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)',
        }}>
          Library
        </h1>
        <p style={{ margin: '4px 0 0', color: 'var(--ink-2)' }}>
          Knowledge base, documents, and reference material.
        </p>
      </header>
      <DocumentsPanel />
    </div>
  )
}
