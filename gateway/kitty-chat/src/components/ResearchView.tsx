'use client'

import { useState, type CSSProperties, type FormEvent } from 'react'

import { ArtifactCanvas } from '@/components/artifacts/ArtifactCanvas'
import { describeFailure } from '@/lib/failure-copy'
import type { GatewayResearchRun } from '@/lib/gateway'
import { useActiveProject, useArtifact, useResearchRuns, useStartResearch } from '@/lib/queries'

export default function ResearchView({ isMobile = false }: { isMobile?: boolean }) {
  const runs = useResearchRuns()
  const start = useStartResearch()
  const activeProject = useActiveProject()
  const [topic, setTopic] = useState('')
  const [previewArtifactId, setPreviewArtifactId] = useState<string | null>(null)
  const projectId = activeProject.data?.project_id ?? null
  const projectName = activeProject.data?.project?.name ?? null
  const projectScopeLoading = activeProject.isLoading
  const projectScopeError = activeProject.error
  const projectScopeKnown = !projectScopeLoading && !projectScopeError

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = topic.trim()
    if (!trimmed || start.isPending || !projectScopeKnown) return
    await start.mutateAsync({ topic: trimmed, project_id: projectId })
    setTopic('')
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '18px 12px 120px' : '28px 30px 56px', background: 'var(--color-canvas)' }}>
      <div style={{ width: '100%', maxWidth: 980, margin: '0 auto', display: 'grid', gap: 18 }}>
        <header>
          <div style={eyebrowStyle}>deep research</div>
          <h1 style={titleStyle}>Research</h1>
          <p style={subtitleStyle}>Watch sources arrive, follow the run, and keep the finished report as a Kitty artifact.</p>
        </header>

        <form onSubmit={onSubmit} style={composerStyle}>
          <textarea
            aria-label="Research topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="What should Kitty investigate deeply?"
            rows={isMobile ? 3 : 2}
            style={textareaStyle}
          />
          <div style={composerFooterStyle}>
            <span style={metaStyle}>
              {projectScopeLoading
                ? 'Checking active project…'
                : projectScopeError
                  ? 'Active project unavailable'
                  : projectName
                    ? `Attach report to ${projectName}`
                    : 'No active project — report stays in Library'}
            </span>
            <button type="submit" aria-label="Start research" disabled={!topic.trim() || start.isPending || !projectScopeKnown} style={primaryButtonStyle}>
              {start.isPending ? 'Starting…' : 'Start research'}
            </button>
          </div>
          {projectScopeError && <p role="alert" style={errorStyle}>{describeFailure(projectScopeError)}</p>}
          {start.error && <p role="alert" style={errorStyle}>{describeFailure(start.error)}</p>}
        </form>

        <section aria-label="Research runs" style={{ display: 'grid', gap: 10 }}>
          <div style={sectionHeaderStyle}><h2 style={sectionTitleStyle}>Runs</h2><span style={metaStyle}>{runs.data?.runs.length ?? 0} recent</span></div>
          {runs.isLoading && !runs.data && <p style={mutedStyle}>Reading research runs…</p>}
          {runs.error && <p role="alert" style={errorStyle}>{describeFailure(runs.error)} {runs.data ? 'Showing the last loaded runs.' : ''}</p>}
          {runs.data?.runs.length === 0 && <div style={emptyStyle}>No research runs yet. Start with a question above.</div>}
          {runs.data?.runs.map((run) => <ResearchRunCard key={run.id} run={run} onOpenReport={setPreviewArtifactId} />)}
        </section>
      </div>
      {previewArtifactId && <ResearchArtifactPreview artifactId={previewArtifactId} isMobile={isMobile} onClose={() => setPreviewArtifactId(null)} />}
    </div>
  )
}

function ResearchRunCard({ run, onOpenReport }: { run: GatewayResearchRun; onOpenReport: (id: string) => void }) {
  return (
    <article style={cardStyle}>
      <div style={{ minWidth: 0, display: 'grid', gap: 8 }}>
        <div style={rowStyle}><span style={statusStyle(run.status)}>{run.stage}</span><span style={metaStyle}>{run.status}</span></div>
        <h3 style={runTitleStyle}>{run.topic}</h3>
        {run.summary && <p style={summaryStyle}>{run.summary}</p>}
        {run.error && <p role="alert" style={errorStyle}>{run.error}</p>}
        {run.sources.length > 0 && (
          <div style={sourceListStyle}>{run.sources.slice(0, 5).map((source) => {
            const href = safeSourceHref(source)
            return href
              ? <a key={source} href={href} target="_blank" rel="noreferrer" style={sourceStyle}>{sourceLabel(source)}</a>
              : <span key={source} style={sourceStyle}>{sourceLabel(source)}</span>
          })}</div>
        )}
      </div>
      {run.artifact_id && <button type="button" aria-label="Open report" onClick={() => onOpenReport(run.artifact_id!)} style={secondaryButtonStyle}>Open report</button>}
    </article>
  )
}

function ResearchArtifactPreview({ artifactId, isMobile, onClose }: { artifactId: string; isMobile: boolean; onClose: () => void }) {
  const artifact = useArtifact(artifactId)
  if (artifact.isLoading) {
    return (
      <div role="dialog" aria-label="Research report preview" style={previewStateStyle}>
        <p style={mutedStyle}>Loading report…</p>
        <button type="button" aria-label="Close report preview" onClick={onClose} style={secondaryButtonStyle}>Close</button>
      </div>
    )
  }
  if (artifact.error || !artifact.data) {
    return (
      <div role="dialog" aria-label="Research report preview" style={previewStateStyle}>
        <p role="alert" style={errorStyle}>{describeFailure(artifact.error ?? new Error('Report artifact is unavailable'))}</p>
        <button type="button" aria-label="Close report preview" onClick={onClose} style={secondaryButtonStyle}>Close</button>
      </div>
    )
  }
  return <ArtifactCanvas artifact={artifact.data} isMobile={isMobile} onClose={onClose} />
}

function safeSourceHref(source: string): string | null {
  try {
    const url = new URL(source)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

function sourceLabel(source: string): string {
  try {
    const host = new URL(source).hostname.replace(/^www\./, '')
    return host || source
  } catch {
    return source
  }
}

function statusStyle(status: string): CSSProperties {
  return { fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: status === 'failed' || status === 'interrupted' ? 'var(--color-destructive)' : 'var(--color-accent)', fontWeight: 700 }
}

const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--color-accent)' }
const titleStyle: CSSProperties = { margin: '4px 0 0', fontFamily: 'var(--font-display)', fontSize: 32, letterSpacing: '-0.03em', color: 'var(--color-text-primary)' }
const subtitleStyle: CSSProperties = { margin: '7px 0 0', maxWidth: 680, fontSize: 13, lineHeight: 1.5, color: 'var(--color-text-secondary)' }
const composerStyle: CSSProperties = { border: '1px solid var(--color-separator)', borderRadius: 14, background: 'var(--color-surface)', padding: 14, display: 'grid', gap: 10, boxShadow: 'var(--shadow-soft)' }
const textareaStyle: CSSProperties = { width: '100%', resize: 'vertical', border: 'none', outline: 'none', background: 'transparent', color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 15, lineHeight: 1.5 }
const composerFooterStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }
const primaryButtonStyle: CSSProperties = { minHeight: 40, padding: '8px 14px', border: 'none', borderRadius: 9, background: 'var(--color-accent)', color: 'var(--on-accent)', fontWeight: 750, cursor: 'pointer' }
const secondaryButtonStyle: CSSProperties = { minHeight: 40, padding: '8px 12px', border: '1px solid var(--color-separator)', borderRadius: 8, background: 'transparent', color: 'var(--color-accent)', fontWeight: 700, cursor: 'pointer', flexShrink: 0 }
const sectionHeaderStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--color-text-primary)' }
const cardStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 14, padding: 14, border: '1px solid var(--color-separator)', borderRadius: 12, background: 'var(--color-surface)' }
const rowStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8 }
const runTitleStyle: CSSProperties = { margin: 0, fontSize: 15, lineHeight: 1.3, color: 'var(--color-text-primary)' }
const summaryStyle: CSSProperties = { margin: 0, fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-secondary)' }
const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-text-secondary)' }
const mutedStyle: CSSProperties = { margin: 0, fontSize: 12, color: 'var(--color-text-secondary)' }
const errorStyle: CSSProperties = { margin: 0, fontSize: 12, color: 'var(--color-destructive)', lineHeight: 1.45 }
const emptyStyle: CSSProperties = { padding: 16, border: '1px dashed var(--color-separator)', borderRadius: 10, color: 'var(--color-text-secondary)', fontSize: 12 }
const sourceListStyle: CSSProperties = { display: 'flex', gap: 7, flexWrap: 'wrap' }
const sourceStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-accent)', textDecoration: 'none', padding: '4px 7px', borderRadius: 999, border: '1px solid var(--color-separator)' }

const previewStateStyle: CSSProperties = { position: 'fixed', inset: 0, zIndex: 80, display: 'grid', placeContent: 'center', gap: 12, padding: 24, background: 'var(--color-canvas)', color: 'var(--color-text-primary)' }
