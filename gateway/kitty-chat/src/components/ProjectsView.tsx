'use client'
import { ProjectsPanel } from '@/components/ProjectsPanel'

export default function ProjectsView({ isMobile }: { isMobile: boolean }) {
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: pad }}>
      <div style={{ width: '100%', maxWidth: 1120, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <header>
          <h1 style={{
            margin: 0, fontFamily: 'var(--font-display)', fontSize: isMobile ? 28 : 32, color: 'var(--color-text-primary)',
          }}>
            Projects
          </h1>
          <p style={{ margin: '5px 0 0', color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.5 }}>
            Keep context, next steps, files, and related work together. Execution stays in Work.
          </p>
        </header>
        <ProjectsPanel />
      </div>
    </div>
  )
}
