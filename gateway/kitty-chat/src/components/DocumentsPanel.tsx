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
  const [validationError, setValidationError] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [abortController, setAbortController] = useState<AbortController | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const Spinner = () => (
    <svg style={{ animation: 'spin 1s linear infinite', width: 14, height: 14 }} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" strokeOpacity="0.25" />
      <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )

  const ALLOWED_TYPES = [
    'application/pdf', 'text/markdown', 'text/plain',
    'image/png', 'image/jpeg', 'image/webp', 'image/gif'
  ]

  function handleFiles(files: FileList | null) {
    setValidationError('')
    setUploadProgress(0)
    const file = files?.[0]
    if (!file) return

    if (!ALLOWED_TYPES.includes(file.type) && !file.name.endsWith('.md')) {
      setValidationError(`unsupported file type: ${file.type || file.name}`)
      return
    }

    if (!upload.isPending) {
      const controller = new AbortController()
      setAbortController(controller)
      upload.mutate({ file, onProgress: setUploadProgress, signal: controller.signal }, {
        onSettled: () => setAbortController(null)
      })
    }
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
            disabled={!query.trim() || searchQuery.isFetching}
            style={{ ...primaryButtonStyle, display: 'flex', gap: 6, alignItems: 'center' }}
          >
            {searchQuery.isFetching && <Spinner />}
            search
          </button>
        </div>

        {submitted && searchQuery.isFetching && <p style={mutedStyle}>searching…</p>}
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
        <div style={sectionLabelStyle}>feed the brain</div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input
              value={target}
              onChange={e => setTarget(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleIngest()}
              placeholder="url or file path..."
              style={inputStyle}
            />
            <button
              onClick={handleIngest}
              disabled={!target.trim() || ingest.isPending}
              style={{ ...primaryButtonStyle, alignSelf: 'flex-start', display: 'flex', gap: 6, alignItems: 'center' }}
            >
              {ingest.isPending && <Spinner />}
              {ingest.isPending ? 'eating…' : 'feed kitty'}
            </button>
            {ingest.isError && (
              <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
                choked — {ingest.error instanceof Error ? ingest.error.message : 'gateway error'}
              </p>
            )}
            {ingest.data && (
              <p style={{ ...mutedStyle, color: STATUS_COLORS[ingest.data.status] ?? 'var(--ink-2)' }}>
                {ingest.data.status}: {ingest.data.reason}
              </p>
            )}
          </div>

          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={e => e.key === 'Enter' && fileInputRef.current?.click()}
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
              width: 120,
              height: 120,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '25px 225px 15px 255px / 255px 15px 225px 15px',
              border: '2px dashed var(--line)',
              borderColor: dragOver ? 'var(--primary)' : 'var(--line)',
              background: dragOver ? 'var(--primary-fade)' : 'var(--surface-2)',
              transform: dragOver ? 'scale(1.05) rotate(2deg)' : 'rotate(-2deg)',
              transition: 'all 0.2s',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {upload.isPending && uploadProgress > 0 && uploadProgress < 100 && (
              <div style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                height: '100%',
                width: `${uploadProgress}%`,
                background: 'var(--primary-fade)',
                zIndex: 0,
                transition: 'width 0.1s linear',
              }} />
            )}

            <div style={{ position: 'relative', zIndex: 1 }}>
              {upload.isPending ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <span>uploading… {uploadProgress}%</span>
                  {abortController && (
                    <button
                      onClick={(e) => { e.stopPropagation(); abortController.abort() }}
                      style={{ ...refreshButtonStyle, marginTop: 4, background: 'var(--bg)' }}
                    >
                      cancel
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>📥</div>
                  <div>drop files</div>
                </>
              )}
            </div>
          </div>
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
        {validationError && (
          <p style={{ ...mutedStyle, color: 'var(--c-yellow)' }}>
            {validationError}
          </p>
        )}
        {upload.data === null && !upload.isPending && upload.isSuccess && (
          <p style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            upload failed — the gateway rejected the file (size or type). check ./kitty logs.
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
  letterSpacing: 0,
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
