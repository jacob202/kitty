'use client'

import { useState, type CSSProperties } from 'react'
import { FileText, Maximize2 } from 'lucide-react'

import { ArtifactCanvas, canPreviewArtifact } from '@/components/artifacts/ArtifactCanvas'
import { describeFailure } from '@/lib/failure-copy'
import { useArtifact } from '@/lib/queries'

export function ArtifactChatCard({ artifactId, isMobile }: { artifactId: string; isMobile: boolean }) {
  const artifact = useArtifact(artifactId)
  const [open, setOpen] = useState(false)

  if (artifact.isLoading) return <div style={cardStyle}>Loading artifact…</div>
  if (artifact.isError || !artifact.data) {
    return <div role="alert" style={cardStyle}>Artifact unavailable — {describeFailure(artifact.error)}</div>
  }

  const item = artifact.data
  const previewable = canPreviewArtifact(item)

  return (
    <>
      <section aria-label={`Artifact: ${item.display_name}`} style={cardStyle}>
        <div style={headerStyle}>
          <FileText size={17} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={eyebrowStyle}>artifact · {item.kind}</div>
            <div style={titleStyle}>{item.display_name}</div>
            <div style={metaStyle}>{item.media_type} · {formatBytes(item.size_bytes)} · {item.state}</div>
          </div>
        </div>
        {previewable ? (
          <button type="button" aria-label="Open artifact" onClick={() => setOpen(true)} style={buttonStyle}>
            <Maximize2 size={14} /> Open
          </button>
        ) : (
          <div style={metaStyle}>Preview unavailable for this artifact state or type.</div>
        )}
      </section>
      {open && <ArtifactCanvas artifact={item} isMobile={isMobile} onClose={() => setOpen(false)} />}
    </>
  )
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'size unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const cardStyle: CSSProperties = { margin: '10px 0', border: '1px solid var(--color-separator)', borderRadius: 12, background: 'var(--color-surface)', padding: 14, display: 'grid', gap: 11, minWidth: 0 }
const headerStyle: CSSProperties = { display: 'flex', gap: 10, alignItems: 'flex-start', color: 'var(--color-text-secondary)' }
const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }
const titleStyle: CSSProperties = { marginTop: 3, fontSize: 15, fontWeight: 750, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }
const metaStyle: CSSProperties = { marginTop: 4, fontSize: 11, color: 'var(--color-text-secondary)' }
const buttonStyle: CSSProperties = { minHeight: 44, justifySelf: 'start', border: '1px solid var(--color-separator)', borderRadius: 9, padding: '8px 13px', background: 'var(--color-surface)', color: 'var(--color-text-primary)', display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontWeight: 650 }
