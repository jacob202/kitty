'use client'

import { useMemo, useState, type CSSProperties } from 'react'
import { RefreshCw, Search } from 'lucide-react'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { useArtifacts } from '@/lib/queries'
import type { GatewayArtifact } from '@/lib/gateway'

export default function LibraryView({ isMobile }: { isMobile: boolean }) {
  const artifacts = useArtifacts()
  const [query, setQuery] = useState('')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'
  const filteredArtifacts = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const items = artifacts.data ?? []
    if (!needle) return items
    return items.filter(artifact => artifactSearchText(artifact).includes(needle))
  }, [artifacts.data, query])

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: pad, minWidth: 0 }}>
      <div style={canvasStyle}>
        <header style={pageHeaderStyle}>
          <h1 style={pageTitleStyle}>Library</h1>
          <p style={pageSubtitleStyle}>Saved outputs, references, and searchable knowledge in one place.</p>
        </header>

        <section aria-label="saved artifacts" style={{ display: 'grid', gap: 12 }}>
          <div style={sectionHeaderStyle}>
            <div>
              <h2 style={sectionTitleStyle}>Saved files</h2>
              <p style={subtitleStyle}>Canonical artifacts stay visible even when knowledge indexing is degraded.</p>
            </div>
            <button
              type="button"
              aria-label="Refresh saved files"
              onClick={() => void artifacts.refetch()}
              disabled={artifacts.isFetching}
              style={{ ...refreshStyle, opacity: artifacts.isFetching ? 0.55 : 1 }}
            >
              <RefreshCw size={15} />
              {artifacts.isFetching ? 'Refreshing' : 'Refresh'}
            </button>
          </div>

          <label style={searchWrapStyle}>
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              aria-label="Search saved files"
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search saved files"
              style={searchInputStyle}
            />
          </label>

          {artifacts.isLoading && <p style={mutedStyle}>Loading saved files…</p>}
          {artifacts.isError && (
            <div role="alert" style={errorStyle}>
              Couldn&apos;t read saved files — {artifactErrorMessage(artifacts.error)}
            </div>
          )}
          {artifacts.data?.length === 0 && <div style={emptyStyle}>No saved files yet.</div>}
          {artifacts.data && artifacts.data.length > 0 && filteredArtifacts.length === 0 && (
            <div style={emptyStyle}>No saved files match “{query.trim()}”.</div>
          )}
          {filteredArtifacts.length > 0 && (
            <div data-testid="library-artifact-list" style={artifactListStyle}>
              {filteredArtifacts.map((artifact, index) => (
                <ArtifactRow key={artifact.id} artifact={artifact} isLast={index === filteredArtifacts.length - 1} />
              ))}
            </div>
          )}
        </section>

        <section aria-label="knowledge index" style={knowledgeSectionStyle}>
          <div>
            <h2 style={sectionTitleStyle}>Knowledge</h2>
            <p style={subtitleStyle}>Searchable derived content. Indexing can be unavailable without hiding saved files.</p>
          </div>
          <DocumentsPanel isMobile={isMobile} />
        </section>
      </div>
    </div>
  )
}

function artifactSearchText(artifact: GatewayArtifact): string {
  return [
    artifact.display_name,
    artifact.kind,
    artifact.media_type,
    artifact.state,
    artifact.created_by,
    artifact.project_id != null ? `project ${artifact.project_id}` : '',
    artifact.conversation_id ? `conversation ${artifact.conversation_id}` : '',
  ].join(' ').toLowerCase()
}

function artifactErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  if (/\b401\b/.test(message)) return 'Sign in again to load saved files.'
  if (/\b403\b/.test(message)) return 'You do not have access to saved files.'
  if (message === 'Saved files returned an invalid response') return `${message}. Try again.`
  return 'Saved files are unavailable right now. Try again.'
}

function ArtifactRow({ artifact, isLast }: { artifact: GatewayArtifact; isLast: boolean }) {
  const provenance = [
    artifact.project_id != null ? `project ${artifact.project_id}` : null,
    artifact.conversation_id ? `conversation ${artifact.conversation_id}` : null,
  ].filter(Boolean)
  const ingestion = typeof artifact.metadata?.ingestion_status === 'string'
    ? artifact.metadata.ingestion_status
    : null

  return (
    <article style={{ ...artifactRowStyle, borderBottom: isLast ? 'none' : '1px solid var(--color-separator)' }}>
      <div style={{ minWidth: 0 }}>
        <div style={artifactNameStyle} title={artifact.display_name}>{artifact.display_name}</div>
        <div style={metaRowStyle}>
          <span>{artifact.kind}</span>
          <span>{artifact.media_type}</span>
          <span>{formatBytes(artifact.size_bytes)}</span>
          <span>{artifact.state}</span>
          {ingestion ? <span>index {ingestion}</span> : null}
        </div>
        {provenance.length > 0 ? <div style={provenanceStyle}>{provenance.map(value => <span key={value}>{value}</span>)}</div> : null}
      </div>
      <time style={timeStyle} dateTime={new Date(artifact.created_at * 1000).toISOString()}>
        {new Date(artifact.created_at * 1000).toLocaleDateString('en-CA')}
      </time>
    </article>
  )
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'size unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const canvasStyle: CSSProperties = { width: '100%', maxWidth: 1120, margin: '0 auto', display: 'grid', gap: 24, alignContent: 'start' }
const pageHeaderStyle: CSSProperties = { display: 'grid', gap: 5 }
const pageTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--color-text-primary)' }
const pageSubtitleStyle: CSSProperties = { margin: 0, color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.5 }
const sectionHeaderStyle: CSSProperties = { display: 'flex', gap: 14, justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--color-text-primary)' }
const subtitleStyle: CSSProperties = { margin: '3px 0 0', color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.45 }
const mutedStyle: CSSProperties = { margin: 0, color: 'var(--color-text-muted)', fontSize: 13 }
const refreshStyle: CSSProperties = { minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7, border: '1px solid var(--color-separator)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)', borderRadius: 'var(--r-control)', padding: '8px 12px', cursor: 'pointer', flexShrink: 0, fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600 }
const searchWrapStyle: CSSProperties = { minHeight: 44, display: 'flex', alignItems: 'center', gap: 8, padding: '0 12px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-text-muted)' }
const searchInputStyle: CSSProperties = { minHeight: 44, width: '100%', border: 0, outline: 0, background: 'transparent', color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 15 }
const artifactListStyle: CSSProperties = { border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)', background: 'var(--color-surface)', overflow: 'hidden' }
const artifactRowStyle: CSSProperties = { minHeight: 72, display: 'flex', gap: 16, justifyContent: 'space-between', alignItems: 'flex-start', padding: '14px 16px', minWidth: 0 }
const artifactNameStyle: CSSProperties = { fontWeight: 650, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 14.5 }
const metaRowStyle: CSSProperties = { display: 'flex', gap: '4px 10px', flexWrap: 'wrap', marginTop: 5, color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 12 }
const provenanceStyle: CSSProperties = { display: 'flex', gap: '4px 10px', flexWrap: 'wrap', marginTop: 5, color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 12 }
const timeStyle: CSSProperties = { color: 'var(--color-text-muted)', fontFamily: 'var(--font-body)', fontSize: 12, flexShrink: 0 }
const emptyStyle: CSSProperties = { padding: 16, border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)', fontSize: 13 }
const errorStyle: CSSProperties = { padding: '12px 14px', border: '1px solid var(--color-destructive)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-destructive)', fontSize: 13 }
const knowledgeSectionStyle: CSSProperties = { display: 'grid', gap: 10, paddingTop: 2 }
