'use client'
import { useRef, useState, type CSSProperties } from 'react'
import { useKnowledgeSources, useKnowledgeSearch, useIngestKnowledge, useUploadCapture } from '@/lib/queries'

const STATUS_COLORS: Record<string, string> = { success: 'var(--color-success)', skipped: 'var(--color-warning)', failed: 'var(--color-destructive)', pending: 'var(--color-accent)' }

export function DocumentsPanel({ isMobile = false }: { isMobile?: boolean }) {
  const sourcesQuery = useKnowledgeSources()
  const ingest = useIngestKnowledge()
  const upload = useUploadCapture()
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const searchQuery = useKnowledgeSearch(submitted)
  const [target, setTarget] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const payload = sourcesQuery.data

  function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (file && !upload.isPending) upload.mutate(file)
  }

  function handleIngest() {
    const value = target.trim()
    if (!value || ingest.isPending) return
    const body = /^https?:\/\//i.test(value) ? { url: value } : { path: value }
    ingest.mutate(body)
  }

  const controlGrid: CSSProperties = {
    display: 'grid', gridTemplateColumns: isMobile ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) auto', gap: 8, minWidth: 0,
  }

  return (
    <div style={{ display: 'grid', gap: 26, alignContent: 'start', minWidth: 0 }}>
      <section aria-labelledby="library-search-heading" style={subsectionStyle}>
        <div>
          <h3 id="library-search-heading" style={subsectionTitleStyle}>Search knowledge</h3>
          <p style={subtitleStyle}>{payload ? `${payload.total_sources} sources · ${payload.total_chunks} indexed chunks` : 'Search everything Kitty has successfully indexed.'}</p>
        </div>
        <div style={controlGrid}>
          <input aria-label="Search library" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && setSubmitted(query.trim())} placeholder="What are you looking for?" style={inputStyle} />
          <button type="button" onClick={() => setSubmitted(query.trim())} disabled={!query.trim()} style={primaryButtonStyle}>Search</button>
        </div>
        {submitted && searchQuery.isLoading && <p style={mutedStyle}>Searching…</p>}
        {submitted && searchQuery.isError && <p style={{ ...mutedStyle, color: 'var(--color-destructive)' }}>Search failed — {searchQuery.error instanceof Error ? searchQuery.error.message : 'gateway error'}</p>}
        {searchQuery.data?.message && <p style={mutedStyle}>{searchQuery.data.message}</p>}
        {(searchQuery.data?.results ?? []).map((r, i) => (
          <article key={i} style={resultStyle}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
              <strong style={resultSourceStyle}>{r.source}</strong>
              {r.reference.page_num != null && <span style={metaStyle}>p. {r.reference.page_num}</span>}
              {typeof r.score === 'number' && <span style={metaStyle}>score {r.score.toFixed(2)}</span>}
            </div>
            <p style={resultTextStyle}>{r.text.slice(0, 320)}{r.text.length > 320 ? '…' : ''}</p>
          </article>
        ))}
      </section>

      <section aria-labelledby="library-add-heading" style={subsectionStyle}>
        <div>
          <h3 id="library-add-heading" style={subsectionTitleStyle}>Add to Library</h3>
          <p style={subtitleStyle}>{isMobile ? 'Paste a URL or choose a file from this device.' : 'Add a URL, enter a file path on this Mac, or choose a file.'}</p>
        </div>
        <div style={controlGrid} data-testid={isMobile ? 'library-url-control' : 'library-path-control'}>
          <input aria-label={isMobile ? 'URL to add' : 'URL or Mac file path'} value={target} onChange={e => setTarget(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleIngest()} placeholder={isMobile ? 'Paste a URL (https://…)' : 'A file path on the Mac, or a URL'} style={inputStyle} />
          <button type="button" onClick={handleIngest} disabled={!target.trim() || ingest.isPending} style={primaryButtonStyle}>{ingest.isPending ? 'Adding…' : isMobile ? 'Add URL' : 'Add'}</button>
        </div>
        {ingest.isError && <p role="status" style={{ ...mutedStyle, color: 'var(--color-destructive)' }}>Ingest failed — {ingest.error instanceof Error ? ingest.error.message : 'gateway error'}</p>}
        {ingest.data && (
          <div style={statusResultStyle}>
            <strong style={{ color: STATUS_COLORS[ingest.data.status] ?? 'var(--color-text-primary)' }}>{ingest.data.status === 'success' ? 'indexed' : ingest.data.status}</strong>
            <span>{ingest.data.reason}</span>
            <details style={detailsStyle}><summary style={detailsSummaryStyle}>Technical details</summary><span style={metaStyle}>{ingest.data.source_id}</span></details>
          </div>
        )}

        <button
          type="button"
          data-testid="library-file-picker"
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click() } }}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
          style={{ ...dropZoneStyle, borderColor: dragOver ? 'var(--color-accent)' : 'var(--color-separator)', background: dragOver ? 'var(--color-selected)' : 'var(--color-surface)' }}
        >
          {upload.isPending ? 'Uploading…' : isMobile ? 'Choose a file (PDF, text, or image)' : 'or drop a file here (pdf / md / txt / images) — choose file'}
        </button>
        <input ref={fileInputRef} type="file" accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,.gif" style={{ display: 'none' }} onChange={e => { handleFiles(e.target.files); e.target.value = '' }} />
        {upload.isError && <p role="status" style={{ ...mutedStyle, color: 'var(--color-destructive)' }}>Upload failed — {upload.error instanceof Error ? upload.error.message : 'gateway error'}</p>}
        {upload.data && <p style={{ ...mutedStyle, color: STATUS_COLORS[upload.data.status] ?? 'var(--color-text-secondary)' }}>{upload.data.status}: {upload.data.message} — it appears under indexed sources when processing finishes.</p>}
      </section>

      <section aria-labelledby="library-sources-heading" style={subsectionStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'space-between' }}>
          <div>
            <h3 id="library-sources-heading" style={subsectionTitleStyle}>Indexed sources</h3>
            <p style={subtitleStyle}>Secondary search metadata; saved artifacts above remain available if this index is degraded.</p>
          </div>
          <button type="button" aria-label="Refresh indexed sources" onClick={() => void sourcesQuery.refetch()} disabled={sourcesQuery.isFetching} style={secondaryButtonStyle}>{sourcesQuery.isFetching ? 'Refreshing…' : 'Refresh'}</button>
        </div>
        {sourcesQuery.isLoading && <p style={mutedStyle}>Loading indexed sources…</p>}
        {sourcesQuery.isError && <p role="status" style={{ ...mutedStyle, color: 'var(--color-destructive)' }}>Couldn&apos;t read the knowledge index — {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : 'gateway error'}.</p>}
        {payload && payload.sources.length === 0 && <p style={mutedStyle}>Nothing indexed yet.</p>}
        {(payload?.sources ?? []).map(s => (
          <article key={s.name} style={sourceRowStyle}>
            <div style={{ minWidth: 0 }}>
              <strong style={sourceNameStyle}>{s.name}</strong>
              {s.primary_topic && <p style={topicStyle}>{s.primary_topic}</p>}
            </div>
            <div style={sourceMetaStyle}>
              <span>{s.collection}</span><span>{s.chunks} chunks</span>{s.ingested_at ? <span>{new Date(s.ingested_at * 1000).toLocaleDateString('en-CA')}</span> : null}
              {s.tags.map(t => <span key={t}>#{t}</span>)}
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}

const subsectionStyle: CSSProperties = { display: 'grid', gap: 12, minWidth: 0, paddingTop: 18, borderTop: '1px solid var(--color-separator)' }
const subsectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 17, fontWeight: 700, color: 'var(--color-text-primary)' }
const subtitleStyle: CSSProperties = { fontSize: 13, lineHeight: 1.5, color: 'var(--color-text-secondary)', margin: '4px 0 0' }
const inputStyle: CSSProperties = { width: '100%', minWidth: 0, minHeight: 44, background: 'var(--color-surface)', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '10px 12px', fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--color-text-primary)', outline: 'none' }
const primaryButtonStyle: CSSProperties = { minHeight: 44, padding: '9px 16px', background: 'var(--color-accent)', color: 'var(--on-accent)', border: 'none', borderRadius: 'var(--r-control)', fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 650, cursor: 'pointer' }
const secondaryButtonStyle: CSSProperties = { minHeight: 44, padding: '8px 13px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface)', color: 'var(--color-text-primary)', fontWeight: 600, flexShrink: 0 }
const mutedStyle: CSSProperties = { margin: 0, fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.55, overflowWrap: 'anywhere' }
const resultStyle: CSSProperties = { padding: '12px 0', borderBottom: '1px solid var(--color-separator)', display: 'grid', gap: 5 }
const resultSourceStyle: CSSProperties = { fontSize: 13, color: 'var(--color-accent)', overflowWrap: 'anywhere' }
const resultTextStyle: CSSProperties = { margin: 0, fontSize: 13, lineHeight: 1.55, color: 'var(--color-text-primary)' }
const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-text-secondary)', overflowWrap: 'anywhere' }
const statusResultStyle: CSSProperties = { padding: '10px 12px', background: 'var(--color-surface-elevated)', borderRadius: 'var(--r-control)', display: 'grid', gap: 3, fontSize: 12, color: 'var(--color-text-secondary)' }
const detailsStyle: CSSProperties = { marginTop: 4 }
const detailsSummaryStyle: CSSProperties = { minHeight: 32, display: 'inline-flex', alignItems: 'center', cursor: 'pointer', fontWeight: 600 }
const dropZoneStyle: CSSProperties = { width: '100%', minHeight: 44, border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)', padding: '12px 14px', fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-secondary)', textAlign: 'center', cursor: 'pointer', lineHeight: 1.45 }
const sourceRowStyle: CSSProperties = { padding: '12px 0', borderBottom: '1px solid var(--color-separator)', display: 'grid', gap: 5, minWidth: 0 }
const sourceNameStyle: CSSProperties = { fontSize: 14, color: 'var(--color-text-primary)', overflowWrap: 'anywhere' }
const topicStyle: CSSProperties = { margin: '3px 0 0', fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5 }
const sourceMetaStyle: CSSProperties = { display: 'flex', gap: '4px 10px', flexWrap: 'wrap', color: 'var(--color-text-secondary)', fontSize: 11 }
