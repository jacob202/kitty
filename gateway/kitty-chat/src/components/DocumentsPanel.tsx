'use client'
import { useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import {
  useKnowledgeSources,
  useKnowledgeSearch,
  useIngestKnowledge,
  useUploadCapture,
} from '@/lib/queries'

const STATUS_COLORS: Record<string, string> = {
  success: 'var(--c-green)',
  skipped: 'var(--c-yellow)',
  failed: 'var(--c-red)',
  pending: 'var(--c-blue)',
}

export function DocumentsPanel() {
  const sourcesQuery = useKnowledgeSources()
  const ingest = useIngestKnowledge()
  const upload = useUploadCapture()

  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const searchQuery = useKnowledgeSearch(submitted)

  const [target, setTarget] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (file && !upload.isPending) upload.mutate(file)
  }

  const payload = sourcesQuery.data

  function handleIngest() {
    const value = target.trim()
    if (!value || ingest.isPending) return
    const body = /^https?:\/\//i.test(value) ? { url: value } : { path: value }
    ingest.mutate(body)
  }

  return (
    <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
      <header>
        <h2 style={titleStyle}>documents</h2>
        <p style={subtitleStyle}>
          {payload
            ? `${payload.total_sources} sources · ${payload.total_chunks} chunks indexed`
            : 'the knowledge library — everything kitty has read and can search.'}
        </p>
      </header>

      {/* ── search ── */}
      <div style={cardStyle}>
        <div style={sectionLabelStyle}>search the library</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && setSubmitted(query.trim())}
            placeholder="what are you looking for?"
            style={inputStyle}
          />
          <button
            onClick={() => setSubmitted(query.trim())}
            disabled={!query.trim()}
            style={primaryButtonStyle}
          >
            search
          </button>
        </div>

        {submitted && searchQuery.isLoading && <p style={mutedStyle}>searching…</p>}
        {submitted && searchQuery.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            search failed —{' '}
            {searchQuery.error instanceof Error ? searchQuery.error.message : 'gateway error'}
          </p>
        )}
        {searchQuery.data?.message && <p style={mutedStyle}>{searchQuery.data.message}</p>}
        {(searchQuery.data?.results ?? []).map((r, i) => (
          <div key={i} style={resultStyle}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
              <span style={resultSourceStyle}>{r.source}</span>
              {r.reference.page_num != null && <span style={metaStyle}>p.{r.reference.page_num}</span>}
              {typeof r.score === 'number' && <span style={metaStyle}>{r.score.toFixed(2)}</span>}
            </div>
            <p style={resultTextStyle}>{r.text.slice(0, 320)}{r.text.length > 320 ? '…' : ''}</p>
          </div>
        ))}
      </div>

      {/* ── ingest ── */}
      <div style={cardStyle}>
        <div style={sectionLabelStyle}>add a document</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={target}
            onChange={e => setTarget(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleIngest()}
            placeholder="a file path on the Mac, or a URL"
            style={inputStyle}
          />
          <button
            onClick={handleIngest}
            disabled={!target.trim() || ingest.isPending}
            style={primaryButtonStyle}
          >
            {ingest.isPending ? 'ingesting…' : 'ingest'}
          </button>
        </div>
        {ingest.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            ingest failed — {ingest.error instanceof Error ? ingest.error.message : 'gateway error'}
          </p>
        )}
        {ingest.data && (
          <p style={{ ...mutedStyle, color: STATUS_COLORS[ingest.data.status] ?? 'var(--ink-2)' }}>
            {ingest.data.status}: {ingest.data.source_id} — {ingest.data.reason}
          </p>
        )}

        <div
          role="button"
          tabIndex={0}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={e => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              fileInputRef.current?.click()
            }
          }}
          onDragOver={e => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => {
            e.preventDefault()
            setDragOver(false)
            handleFiles(e.dataTransfer.files)
          }}
          style={{
            ...dropZoneStyle,
            borderColor: dragOver ? 'var(--primary)' : 'var(--line)',
            background: dragOver ? 'var(--primary-fade)' : 'var(--bg)',
          }}
        >
          {upload.isPending
            ? 'uploading…'
            : 'or drop a file here (pdf / md / txt / images) — uploads via /capture/file, indexes in the background'}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,.gif"
          style={{ display: 'none' }}
          onChange={e => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
        {upload.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            upload failed —{' '}
            {upload.error instanceof Error ? upload.error.message : 'gateway error'}
          </p>
        )}
        {upload.data === null && !upload.isPending && upload.isSuccess && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            upload failed — the file may be too large or the wrong type.
          </p>
        )}
        {upload.data && (
          <p style={{ ...mutedStyle, color: STATUS_COLORS[upload.data.status] ?? 'var(--ink-2)' }}>
            {upload.data.status}: {upload.data.message} — it appears under sources once indexing
            finishes (refresh below).
          </p>
        )}
      </div>

      {/* ── sources ── */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ ...sectionLabelStyle, borderBottom: 'none', paddingBottom: 0, flex: 1 }}>
            sources
          </span>
          <button
            onClick={() => void sourcesQuery.refetch()}
            disabled={sourcesQuery.isFetching}
            style={refreshButtonStyle}
          >
            {sourcesQuery.isFetching ? '…' : '↻ refresh'}
          </button>
        </div>
        {sourcesQuery.isLoading && <p style={mutedStyle}>loading sources…</p>}
        {sourcesQuery.isError && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            couldn&apos;t read the library —{' '}
            {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : 'gateway error'}.
            GET /knowledge/sources didn&apos;t answer; is the gateway up?
          </p>
        )}
        {payload && payload.sources.length === 0 && (
          <p style={mutedStyle}>library is empty — ingest something above.</p>
        )}
        {(payload?.sources ?? []).map(s => (
          <div key={s.name} style={sourceRowStyle}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
              <span style={sourceNameStyle}>{s.name}</span>
              <span style={chipStyle}>{s.collection}</span>
              {s.tags.map(t => (
                <span key={t} style={{ ...chipStyle, color: 'var(--c-blue)' }}>#{t}</span>
              ))}
              <span style={{ flex: 1 }} />
              <span style={metaStyle}>{s.chunks} chunks</span>
            </div>
            {s.primary_topic && <p style={topicStyle}>{s.primary_topic}</p>}
            {s.ingested_at ? (
              <span style={metaStyle}>
                ingested {new Date(s.ingested_at * 1000).toLocaleDateString('en-CA')}
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 800,
  fontSize: 28,
  letterSpacing: '-0.02em',
  color: 'var(--ink)',
}

const subtitleStyle: CSSProperties = {
  fontSize: 13,
  color: 'var(--ink-2)',
  marginTop: 2,
}

const cardStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  borderRadius: 14,
  padding: 18,
  display: 'grid',
  gap: 10,
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'lowercase',
  color: 'var(--ink-2)',
  paddingBottom: 6,
  borderBottom: '1px solid var(--line)',
}

const inputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--bg)',
  border: '1.5px solid var(--line)',
  borderRadius: 10,
  padding: '8px 12px',
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  color: 'var(--ink)',
  outline: 'none',
}

const primaryButtonStyle: CSSProperties = {
  padding: '8px 18px',
  background: 'var(--primary)',
  color: 'var(--on-primary)',
  border: 'none',
  borderRadius: 10,
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
}

const resultStyle: CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--line)',
  borderRadius: 10,
  padding: '8px 12px',
  display: 'grid',
  gap: 4,
}

const resultSourceStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--primary)',
}

const resultTextStyle: CSSProperties = {
  fontSize: 13,
  lineHeight: 1.55,
  color: 'var(--ink)',
}

const sourceRowStyle: CSSProperties = {
  padding: '8px 0',
  borderBottom: '1px solid var(--line)',
  display: 'grid',
  gap: 4,
}

const sourceNameStyle: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--ink)',
}

const topicStyle: CSSProperties = {
  fontSize: 12,
  color: 'var(--ink-2)',
  lineHeight: 1.5,
}

const chipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.06em',
  padding: '2px 8px',
  border: '1px solid var(--line)',
  borderRadius: 999,
  color: 'var(--ink-2)',
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const mutedStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--ink-2)',
  lineHeight: 1.6,
}

const dropZoneStyle: CSSProperties = {
  border: '1.5px dashed var(--line)',
  borderRadius: 10,
  padding: '14px 12px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  textAlign: 'center',
  cursor: 'pointer',
  lineHeight: 1.5,
}

const refreshButtonStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '3px 10px',
  border: '1px solid var(--line)',
  borderRadius: 8,
  background: 'var(--surface-2)',
  color: 'var(--ink-2)',
  cursor: 'pointer',
}
