'use client'
import { useState } from 'react'
import { ProjectsPanel } from '@/components/ProjectsPanel'
import { DocumentsPanel } from '@/components/DocumentsPanel'

export default function LibraryView({ isMobile }: { isMobile: boolean }) {
  const [filter, setFilter] = useState('all')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 4 }}>
        {[
          { id: 'all', label: 'All' },
          { id: 'projects', label: 'Projects' },
          { id: 'docs', label: 'Documents' },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: '4px 12px', fontSize: 11, fontFamily: 'var(--font-mono)',
              border: '1.5px solid var(--line)', borderRadius: 99,
              background: filter === f.id ? 'var(--ginger-fade)' : 'transparent',
              color: filter === f.id ? 'var(--cat-ginger)' : 'var(--ink-2)',
              cursor: 'pointer',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>
      {(filter === 'all' || filter === 'projects') && <ProjectsPanel />}
      {(filter === 'all' || filter === 'docs') && <DocumentsPanel />}
    </div>
  )
}
