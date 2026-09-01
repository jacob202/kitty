'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ExternalLink, MessageSquare, X } from 'lucide-react'

import {
  artifactContentUrl,
  fetchArtifactText,
  type GatewayArtifact,
} from '@/lib/gateway'
import { describeFailure } from '@/lib/failure-copy'
import { useDialogFocus } from '@/hooks/useDialogFocus'

const PREVIEWABLE_MEDIA = new Set([
  'application/pdf',
  'image/gif',
  'image/jpeg',
  'image/png',
  'image/webp',
  'text/markdown',
  'text/plain',
  'text/x-markdown',
])

export function canPreviewArtifact(artifact: GatewayArtifact): boolean {
  return artifact.state === 'ready' && PREVIEWABLE_MEDIA.has(artifact.media_type.toLowerCase())
}

export function ArtifactCanvas({
  artifact,
  isMobile,
  onClose,
  onUseInChat,
  actionError,
}: {
  artifact: GatewayArtifact
  isMobile: boolean
  onClose: () => void
  onUseInChat?: () => void
  actionError?: string | null
}) {
  const mediaType = artifact.media_type.toLowerCase()
  const isMarkdown = mediaType === 'text/markdown' || mediaType === 'text/x-markdown'
  const isText = isMarkdown || mediaType === 'text/plain'
  const isImage = mediaType.startsWith('image/')
  const isPdf = mediaType === 'application/pdf'
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const dialogRef = useDialogFocus<HTMLElement>({ open: true, onClose })

  useEffect(() => {
    if (!isText) {
      setText(null)
      setError(null)
      return
    }
    let active = true
    const controller = new AbortController()
    setText(null)
    setError(null)
    void fetchArtifactText(artifact.id, controller.signal)
      .then((value) => { if (active) setText(value) })
      .catch((err) => {
        if (!active || (err instanceof Error && err.name === 'AbortError')) return
        const explained = err instanceof Error && err.name === 'ArtifactPreviewRejection'
        setError(explained ? err.message : describeFailure(err))
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [artifact.id, isText])

  const contentUrl = artifactContentUrl(artifact.id)

  return (
    <div style={backdropStyle} onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={artifact.display_name}
        style={{ ...canvasStyle, width: isMobile ? '100%' : 'min(760px, 62vw)' }}
      >
        <header style={headerStyle}>
          <div style={{ minWidth: 0 }}>
            <div style={eyebrowStyle}>artifact</div>
            <h2 style={titleStyle}>{artifact.display_name}</h2>
            <div style={metaStyle}>{artifact.media_type} · {formatBytes(artifact.size_bytes)}</div>
          </div>
          <button type="button" aria-label="Close artifact" onClick={onClose} style={iconButtonStyle}>
            <X size={18} />
          </button>
        </header>

        <div style={bodyStyle}>
          {isImage && !error && (
            <div style={imageStageStyle}>
              {/* The Gateway resolves the registered ArtifactStore path by id. */}
              <img
                src={contentUrl}
                alt={artifact.display_name}
                style={imageStyle}
                onError={() => setError('This saved image could not be loaded. Refresh Library or re-import the file.')}
              />
            </div>
          )}
          {isPdf && (
            <iframe title={`Preview ${artifact.display_name}`} src={contentUrl} style={pdfStyle} />
          )}
          {isText && text === null && !error && <p style={mutedStyle}>Loading artifact…</p>}
          {error && <p role="alert" style={errorStyle}>{error}</p>}
          {isMarkdown && text !== null && !error && (
            <article className="artifact-markdown" style={markdownStyle}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  img: ({ alt }) => (
                    <span role="note" style={mutedStyle}>
                      {alt ? `${alt}: ` : ''}Remote image blocked. Open it separately only if you trust the source.
                    </span>
                  ),
                }}
              >
                {text}
              </ReactMarkdown>
            </article>
          )}
          {mediaType === 'text/plain' && text !== null && !error && <pre style={preStyle}>{text}</pre>}
          {!isImage && !isPdf && !isText && (
            <p style={mutedStyle}>Preview unavailable for {artifact.media_type}.</p>
          )}
        </div>

        <footer style={footerStyle}>
          {actionError && <p role="alert" style={errorStyle}>{actionError}</p>}
          {onUseInChat && (
            <button type="button" onClick={onUseInChat} style={actionButtonStyle}>
              <MessageSquare size={14} /> Use in chat
            </button>
          )}
          <a href={contentUrl} target="_blank" rel="noreferrer" style={secondaryActionStyle}>
            <ExternalLink size={14} /> Open raw
          </a>
        </footer>
      </section>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'size unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const backdropStyle: CSSProperties = { position: 'fixed', inset: 0, zIndex: 1200, background: 'rgba(0, 0, 0, 0.48)', display: 'flex', justifyContent: 'flex-end' }
const canvasStyle: CSSProperties = { height: '100%', background: 'var(--color-background, var(--bg))', borderLeft: '1px solid var(--color-separator, var(--line))', boxShadow: '-20px 0 50px rgba(0,0,0,0.22)', display: 'flex', flexDirection: 'column', minWidth: 0 }
const headerStyle: CSSProperties = { minHeight: 76, padding: '16px 18px', borderBottom: '1px solid var(--color-separator, var(--line))', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }
const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--color-text-secondary, var(--ink-2))' }
const titleStyle: CSSProperties = { margin: '3px 0 0', fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--color-text-primary, var(--ink))', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }
const metaStyle: CSSProperties = { marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-text-secondary, var(--ink-2))' }
const iconButtonStyle: CSSProperties = { width: 44, height: 44, border: '1px solid var(--color-separator, var(--line))', borderRadius: 'var(--r-control, 8px)', background: 'var(--color-surface, var(--surface))', color: 'var(--color-text-primary, var(--ink))', display: 'grid', placeItems: 'center', cursor: 'pointer', flexShrink: 0 }
const bodyStyle: CSSProperties = { flex: 1, minHeight: 0, overflow: 'auto', padding: 22 }
const imageStageStyle: CSSProperties = { width: '100%', height: '100%', minHeight: 320, display: 'grid', placeItems: 'center', background: 'var(--color-surface, var(--surface))', border: '1px solid var(--color-separator, var(--line))', borderRadius: 10, overflow: 'hidden' }
const imageStyle: CSSProperties = { display: 'block', maxWidth: '100%', maxHeight: 'calc(100vh - 190px)', objectFit: 'contain' }
const pdfStyle: CSSProperties = { width: '100%', height: '100%', minHeight: 'calc(100vh - 190px)', border: '1px solid var(--color-separator, var(--line))', borderRadius: 8, background: 'white' }
const markdownStyle: CSSProperties = { maxWidth: 760, margin: '0 auto', fontFamily: 'var(--font-body)', color: 'var(--color-text-primary, var(--ink))', lineHeight: 1.65, overflowWrap: 'anywhere' }
const preStyle: CSSProperties = { margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6, color: 'var(--color-text-primary, var(--ink))' }
const mutedStyle: CSSProperties = { margin: 0, color: 'var(--color-text-secondary, var(--ink-2))', fontSize: 13 }
const errorStyle: CSSProperties = { ...mutedStyle, color: 'var(--color-destructive)' }
const footerStyle: CSSProperties = { minHeight: 68, padding: '12px 18px', paddingBottom: 'calc(12px + env(safe-area-inset-bottom, 0px))', borderTop: '1px solid var(--color-separator, var(--line))', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }
const actionButtonStyle: CSSProperties = { minHeight: 44, border: 'none', borderRadius: 'var(--r-control, 8px)', background: 'var(--color-accent, var(--primary))', color: 'white', padding: '9px 14px', display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontWeight: 650 }
const secondaryActionStyle: CSSProperties = { minHeight: 44, border: '1px solid var(--color-separator, var(--line))', borderRadius: 'var(--r-control, 8px)', color: 'var(--color-text-primary, var(--ink))', textDecoration: 'none', padding: '9px 14px', display: 'inline-flex', alignItems: 'center', gap: 7, boxSizing: 'border-box', fontSize: 13, fontWeight: 650 }
