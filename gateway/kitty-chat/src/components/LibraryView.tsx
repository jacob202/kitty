'use client'
import type { CSSProperties } from 'react'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { useArtifacts } from '@/lib/queries'
import type { GatewayArtifact } from '@/lib/gateway'

export default function LibraryView({ isMobile }: { isMobile: boolean }) {
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'
  const artifacts = useArtifacts()

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>
          Library
        </h1>
        <p style={{ margin: '4px 0 0', color: 'var(--ink-2)' }}>
          Saved files first; searchable knowledge when indexing is available.
        </p>
      </header>

      <section style={cardStyle} aria-label="saved artifacts">
        <div style={sectionHeaderStyle}>
          <div>
            <h2 style={sectionTitleStyle}>saved files</h2>
            <p style={subtitleStyle}>Canonical artifacts — capture and generated outputs appear here before indexing.</p>
          </div>
          <button onClick={() => void artifacts.refetch()} disabled={artifacts.isFetching} style={refreshStyle}>
            {artifacts.isFetching ? '…' : '↻ refresh'}
          </button>
        </div>

        {artifacts.isLoading && <p style={mutedStyle}>loading saved files…</p>}
        {artifacts.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            couldn&apos;t read saved files — {artifacts.error instanceof Error ? artifacts.error.message : 'gateway error'}.
          </p>
        )}
        {artifacts.data?.length === 0 && <p style={mutedStyle}>no saved files yet.</p>}
        {(artifacts.data ?? []).map(artifact => <ArtifactRow key={artifact.id} artifact={artifact} />)}
      </section>

      <section aria-label="knowledge index" style={{ display: 'grid', gap: 8 }}>
        <div>
          <h2 style={sectionTitleStyle}>knowledge index</h2>
          <p style={subtitleStyle}>Derived searchable content. Indexing can be degraded without hiding saved files.</p>
        </div>
        <DocumentsPanel isMobile={isMobile} />
      </section>
    </div>
  )
}

function ArtifactRow({ artifact }: { artifact: GatewayArtifact }) {
  const provenance = [
    artifact.project_id != null ? `project ${artifact.project_id}` : null,
    artifact.conversation_id ? `conversation ${artifact.conversation_id}` : null,
  ].filter(Boolean)
  const ingestion = typeof artifact.metadata?.ingestion_status === 'string'
    ? artifact.metadata.ingestion_status
    : null

  return (
    <article style={artifactRowStyle}>
      <div style={{ minWidth: 0 }}>
        <div style={artifactNameStyle}>{artifact.display_name}</div>
        <div style={metaRowStyle}>
          <span>{artifact.kind}</span>
          <span>{artifact.media_type}</span>
          <span>{formatBytes(artifact.size_bytes)}</span>
          <span>{artifact.state}</span>
          {ingestion ? <span>index {ingestion}</span> : null}
        </div>
        {provenance.length > 0 ? <div style={metaRowStyle}>{provenance.map(value => <span key={value}>{value}</span>)}</div> : null}
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

const cardStyle: CSSProperties = { padding: 16, border: '1px solid var(--line)', borderRadius: 8, background: 'var(--surface)', display: 'grid', gap: 10, minWidth: 0 }
const sectionHeaderStyle: CSSProperties = { display: 'flex', gap: 12, justifyContent: 'space-between', alignItems: 'flex-start' }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--ink)' }
const subtitleStyle: CSSProperties = { margin: '3px 0 0', color: 'var(--ink-2)', fontSize: 12 }
const mutedStyle: CSSProperties = { margin: 0, color: 'var(--ink-2)', fontSize: 12 }
const refreshStyle: CSSProperties = { border: '1px solid var(--line)', background: 'transparent', color: 'var(--ink-2)', borderRadius: 4, padding: '4px 8px', cursor: 'pointer', flexShrink: 0 }
const artifactRowStyle: CSSProperties = { display: 'flex', gap: 12, justifyContent: 'space-between', alignItems: 'flex-start', padding: '10px 0', borderTop: '1px solid var(--line)', minWidth: 0 }
const artifactNameStyle: CSSProperties = { fontWeight: 650, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }
const metaRowStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 10 }
const timeStyle: CSSProperties = { color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 10, flexShrink: 0 }
