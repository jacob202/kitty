'use client'
import { useState, type CSSProperties } from 'react'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { ArtifactCanvas, canPreviewArtifact } from '@/components/artifacts/ArtifactCanvas'
import { useArtifacts } from '@/lib/queries'
import type { GatewayArtifact, ChatImageAttachment } from '@/lib/gateway'
import { setArtifactArchived, useArtifactInChat } from '@/lib/gateway'
import { describeFailure } from '@/lib/failure-copy'
import { useKitty } from '@/state/KittyContext'

const CHAT_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])

export default function LibraryView({ isMobile }: { isMobile: boolean }) {
  const { setAttachments, setActiveView } = useKitty()
  const [useError, setUseError] = useState<string | null>(null)
  const [selectedArtifact, setSelectedArtifact] = useState<GatewayArtifact | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [archivePendingId, setArchivePendingId] = useState<string | null>(null)
  const [archiveError, setArchiveError] = useState<string | null>(null)
  const pad = isMobile ? '20px 16px 124px' : '32px 40px 48px'
  const artifacts = useArtifacts(100, showArchived)
  const recentArtifacts = [...(artifacts.data ?? [])].sort((a, b) => b.created_at - a.created_at)

  const handleArchive = async (artifact: GatewayArtifact) => {
    const shouldArchive = artifact.state !== 'archived'
    setArchiveError(null)
    setArchivePendingId(artifact.id)
    try {
      await setArtifactArchived(artifact.id, shouldArchive)
      if (selectedArtifact?.id === artifact.id) setSelectedArtifact(null)
      await artifacts.refetch()
    } catch (err) {
      setArchiveError(describeFailure(err))
    } finally {
      setArchivePendingId(null)
    }
  }

  const handleUseInChat = async (artifact: GatewayArtifact) => {
    setUseError(null)
    try {
      const attachment: ChatImageAttachment = await useArtifactInChat(artifact.id)
      setAttachments((prev) => [...prev.filter((a) => a.id !== attachment.id), attachment])
      setActiveView('chat')
    } catch (err) {
      const explained = err instanceof Error && err.name === 'ArtifactChatRejection'
      setUseError(explained ? (err as Error).message : describeFailure(err))
    }
  }

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 28, minWidth: 0 }}>
      <header style={{ maxWidth: 720 }}>
        <h1 style={pageTitleStyle}>Library</h1>
        <p style={pageSubtitleStyle}>Your saved files and generated artifacts, with searchable knowledge when indexing is available.</p>
      </header>

      <section aria-labelledby="recent-artifacts-heading" style={sectionStyle}>
        <div style={sectionHeaderStyle}>
          <div style={{ minWidth: 0, flex: '1 1 220px' }}>
            <h2 id="recent-artifacts-heading" style={sectionTitleStyle}>Recent artifacts</h2>
            <p style={subtitleStyle}>Saved outputs are canonical here even when search indexing is delayed or unavailable.</p>
          </div>
          <div style={headerActionsStyle}>
            <button
              type="button"
              aria-pressed={showArchived}
              onClick={() => setShowArchived((current) => !current)}
              style={refreshStyle}
            >
              {showArchived ? 'Hide archived' : 'Show archived'}
            </button>
            <button
              type="button"
              aria-label="Refresh artifacts"
              onClick={() => void artifacts.refetch()}
              disabled={artifacts.isFetching}
              style={refreshStyle}
            >
              {artifacts.isFetching ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>

        {artifacts.isLoading && <p style={mutedStyle}>Loading artifacts…</p>}
        {artifacts.isError && (
          <p role="status" style={{ ...mutedStyle, color: 'var(--color-destructive)' }}>
            Couldn&apos;t read saved files — {artifactErrorMessage(artifacts.error)}
          </p>
        )}
        {artifacts.data?.length === 0 && <p style={emptyStyle}>No saved artifacts yet. Add a file below to get started.</p>}
        {recentArtifacts.length > 0 && (
          <ul aria-label="Recent artifacts" style={artifactListStyle}>
            {recentArtifacts.map(artifact => (
              <ArtifactRow
                key={artifact.id}
                artifact={artifact}
                onOpen={() => { setUseError(null); setSelectedArtifact(artifact) }}
                onUseInChat={() => void handleUseInChat(artifact)}
                onArchive={() => void handleArchive(artifact)}
                archivePending={archivePendingId === artifact.id}
              />
            ))}
          </ul>
        )}
        {(useError || archiveError) && (
          <p role="alert" style={{ ...mutedStyle, color: 'var(--color-destructive)', marginTop: 10 }}>
            {useError ?? archiveError}
          </p>
        )}
      </section>

      {selectedArtifact && (
        <ArtifactCanvas
          artifact={selectedArtifact}
          isMobile={isMobile}
          onClose={() => setSelectedArtifact(null)}
          onUseInChat={isChatReady(selectedArtifact) ? () => void handleUseInChat(selectedArtifact) : undefined}
          actionError={useError}
        />
      )}

      <section aria-labelledby="library-knowledge-heading" style={sectionStyle}>
        <div>
          <h2 id="library-knowledge-heading" style={sectionTitleStyle}>Search & add</h2>
          <p style={subtitleStyle}>Search indexed content, add a URL, choose a file, or review what Kitty has indexed.</p>
        </div>
        <DocumentsPanel isMobile={isMobile} />
      </section>
    </div>
  )
}

function artifactErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  if (message === 'Saved files returned an invalid response') return `${message}. Try again.`
  return describeFailure(error)
}

function ArtifactRow({ artifact, onOpen, onUseInChat, onArchive, archivePending }: { artifact: GatewayArtifact; onOpen: () => void; onUseInChat: () => void; onArchive: () => void; archivePending: boolean }) {
  const ingestion = typeof artifact.metadata?.ingestion_status === 'string' ? artifact.metadata.ingestion_status : null
  const created = new Date(artifact.created_at * 1000)
  const backingMissing = artifact.storage_available === false
  const state = backingMissing ? 'Missing' : humanize(artifact.state)
  const isImage = artifact.media_type.startsWith('image/')
  const chatReady = isChatReady(artifact)
  const previewReady = canPreviewArtifact(artifact)
  const chatUnavailableReason = backingMissing
    ? 'This saved file is missing from disk. Re-import it to use it again.'
    : artifact.state === 'archived'
      ? 'Restore this file before using it in chat.'
      : !isImage
    ? 'Only images can be attached into a chat message from Library.'
    : artifact.state !== 'ready'
      ? 'This file is not ready to use in chat yet.'
      : 'This image type isn\u2019t supported in chat yet — use PNG, JPEG, or WebP.'

  return (
    <li style={artifactItemStyle}>
      <article style={{ minWidth: 0 }}>
        <div style={artifactTopStyle}>
          <div style={{ minWidth: 0 }}>
            <div style={artifactNameStyle}>{artifact.display_name}</div>
            <div style={primaryMetaStyle}>
              <span>{artifactTypeLabel(artifact)}</span>
              <span aria-hidden="true">·</span>
              <span>{formatBytes(artifact.size_bytes)}</span>
              <span aria-hidden="true">·</span>
              <span style={statusStyle(backingMissing ? 'missing' : artifact.state)}>{state}</span>
            </div>
          </div>
          <time style={timeStyle} dateTime={created.toISOString()}>{created.toLocaleDateString('en-CA')}</time>
        </div>

        <div style={artifactActionsStyle}>
          {previewReady && (
            <button
              type="button"
              onClick={onOpen}
              aria-label={`Open ${artifact.display_name}`}
              style={openButtonStyle}
            >
              Open
            </button>
          )}
          {chatReady ? (
            <button
              type="button"
              onClick={onUseInChat}
              aria-label={`Use ${artifact.display_name} in chat`}
              style={useButtonStyle}
            >
              Use in chat
            </button>
          ) : (
            <button
              type="button"
              aria-label={`Use ${artifact.display_name} in chat unavailable`}
              disabled
              style={{ ...useButtonStyle, cursor: 'not-allowed', opacity: 0.6, color: 'var(--color-text-secondary)' }}
            >
              Use in chat unavailable
            </button>
          )}
          <button
            type="button"
            aria-label={`${artifact.state === 'archived' ? 'Restore' : 'Archive'} ${artifact.display_name}`}
            onClick={onArchive}
            disabled={archivePending}
            style={secondaryButtonStyle}
          >
            {archivePending ? 'Saving…' : artifact.state === 'archived' ? 'Restore' : 'Archive'}
          </button>
          {!chatReady && <span style={openUnavailableStyle}>{chatUnavailableReason}</span>}
        </div>

        <details style={detailsStyle}>
          <summary style={detailsSummaryStyle}>Details</summary>
          <div style={technicalGridStyle}>
            <span>Type: {artifact.kind}</span>
            <span>Media: {artifact.media_type}</span>
            {ingestion ? <span>Index: {humanize(ingestion)}</span> : null}
            {artifact.project_id != null ? <span>Project {artifact.project_id}</span> : null}
            {artifact.conversation_id ? <span>Conversation {artifact.conversation_id}</span> : null}
            {artifact.error ? <span style={{ color: 'var(--color-destructive)' }}>Error: {artifact.error}</span> : null}
          </div>
        </details>
      </article>
    </li>
  )
}


function isChatReady(artifact: GatewayArtifact): boolean {
  return artifact.media_type.startsWith('image/')
    && artifact.state === 'ready'
    && artifact.storage_available !== false
    && CHAT_IMAGE_TYPES.has(artifact.media_type)
}

function artifactTypeLabel(artifact: GatewayArtifact): string {
  if (artifact.media_type.startsWith('image/')) return 'Image'
  if (artifact.media_type === 'application/pdf') return 'PDF'
  if (artifact.media_type.startsWith('text/')) return 'Text'
  if (artifact.kind.toLowerCase() === 'document') return 'Document'
  return humanize(artifact.kind)
}

function humanize(value: string): string {
  const spaced = value.replace(/[_-]+/g, ' ').trim()
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : 'Unknown'
}

function statusStyle(state: string): CSSProperties {
  const normalized = state.toLowerCase()
  const color = normalized === 'ready' || normalized === 'success'
    ? 'var(--color-success)'
    : normalized === 'failed' || normalized === 'error' || normalized === 'unavailable' || normalized === 'missing'
      ? 'var(--color-destructive)'
      : 'var(--color-text-secondary)'
  return { color, fontWeight: 650 }
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'Size unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const pageTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 34, lineHeight: 1.15, letterSpacing: '-0.025em', color: 'var(--color-text-primary)' }
const pageSubtitleStyle: CSSProperties = { margin: '8px 0 0', color: 'var(--color-text-secondary)', fontSize: 15, lineHeight: 1.55 }
const sectionStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 14, minWidth: 0, width: '100%', maxWidth: 960 }
const sectionHeaderStyle: CSSProperties = { display: 'flex', gap: 12, justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', minWidth: 0 }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 21, fontWeight: 700, color: 'var(--color-text-primary)' }
const subtitleStyle: CSSProperties = { margin: '4px 0 0', color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.5, maxWidth: 680 }
const mutedStyle: CSSProperties = { margin: 0, color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.5 }
const emptyStyle: CSSProperties = { ...mutedStyle, padding: '20px 0', borderTop: '1px solid var(--color-separator)' }
const headerActionsStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap' }
const refreshStyle: CSSProperties = { border: '1px solid var(--color-separator)', background: 'var(--color-surface)', color: 'var(--color-text-primary)', borderRadius: 'var(--r-control)', padding: '8px 14px', minHeight: 44, cursor: 'pointer', flexShrink: 0, fontWeight: 600 }
const artifactListStyle: CSSProperties = { listStyle: 'none', margin: 0, padding: 0, borderTop: '1px solid var(--color-separator)' }
const artifactItemStyle: CSSProperties = { listStyle: 'none', padding: '16px 0', borderBottom: '1px solid var(--color-separator)', minWidth: 0 }
const artifactTopStyle: CSSProperties = { display: 'flex', gap: 14, justifyContent: 'space-between', alignItems: 'flex-start', minWidth: 0 }
const artifactNameStyle: CSSProperties = { fontSize: 15, fontWeight: 650, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }
const primaryMetaStyle: CSSProperties = { display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 5, color: 'var(--color-text-secondary)', fontSize: 12, lineHeight: 1.4 }
const timeStyle: CSSProperties = { color: 'var(--color-text-secondary)', fontSize: 12, flexShrink: 0, paddingTop: 2 }
const detailsStyle: CSSProperties = { marginTop: 8, color: 'var(--color-text-secondary)', fontSize: 12 }
const detailsSummaryStyle: CSSProperties = { cursor: 'pointer', minHeight: 32, display: 'inline-flex', alignItems: 'center', fontWeight: 600 }
const artifactActionsStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: '8px 12px', flexWrap: 'wrap', marginTop: 10 }
const openButtonStyle: CSSProperties = { minHeight: 44, border: 'none', background: 'var(--color-accent)', color: 'white', borderRadius: 'var(--r-control)', padding: '8px 13px', fontSize: 13, fontWeight: 700, cursor: 'pointer' }
const useButtonStyle: CSSProperties = { minHeight: 44, border: '1px solid var(--color-separator)', background: 'var(--color-surface)', color: 'var(--color-accent)', borderRadius: 'var(--r-control)', padding: '8px 12px', fontSize: 13, fontWeight: 650, cursor: 'pointer' }
const openUnavailableStyle: CSSProperties = { color: 'var(--color-text-secondary)', fontSize: 11, lineHeight: 1.4, maxWidth: 460 }
const technicalGridStyle: CSSProperties = { marginTop: 6, paddingLeft: 14, display: 'flex', gap: '4px 14px', flexWrap: 'wrap', fontFamily: 'var(--font-mono)', fontSize: 10, overflowWrap: 'anywhere' }

const secondaryButtonStyle: CSSProperties = { minHeight: 44, border: '1px solid var(--color-separator)', background: 'transparent', color: 'var(--color-text-secondary)', borderRadius: 'var(--r-control)', padding: '8px 12px', fontSize: 13, fontWeight: 650, cursor: 'pointer' }
