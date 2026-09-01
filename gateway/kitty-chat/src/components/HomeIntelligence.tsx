'use client'

import type { GatewayIntelligenceProjection } from '@/lib/gateway'

interface Props {
  projection?: GatewayIntelligenceProjection
  onOpenProject?: (projectId: number) => void
  onDiscuss?: (prompt: string) => void
  onFindConnections?: () => void
  findingConnections?: boolean
  error?: string | null
  refreshError?: string | null
}

const sourceLabel: Record<string, string> = {
  deadline: 'needs you',
  insight: 'returned thought',
  magic: 'connection',
  life: 'today',
}

export function HomeIntelligence({
  projection,
  onOpenProject,
  onDiscuss,
  onFindConnections,
  findingConnections = false,
  error = null,
  refreshError = null,
}: Props) {
  const items = projection?.items.slice(0, 3) ?? []
  const unavailableSources = Object.entries(projection?.sources ?? {})
    .filter(([, source]) => source.state === 'unavailable')
    .map(([name]) => name)
  const degraded = unavailableSources.length > 0
  if (items.length === 0 && !onFindConnections && !error && !refreshError && !degraded) return null

  return (
    <section
      aria-label="Kitty noticed"
      style={{
        border: '1px solid var(--color-separator)', borderRadius: 16,
        background: 'var(--color-surface)', boxShadow: 'var(--shadow-soft)', overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '12px 14px 9px' }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '-0.01em', color: 'var(--color-text-primary)' }}>Kitty noticed</div>
          <div style={{ marginTop: 2, fontSize: 10.5, color: 'var(--color-text-muted)' }}>
            {degraded ? 'best available context · some signals unavailable' : 'from your work, deadlines, and saved thoughts'}
          </div>
        </div>
        {onFindConnections && (
          <button
            type="button"
            onClick={onFindConnections}
            disabled={findingConnections}
            aria-label="Find cross-project connections"
            style={{
              border: '1px solid var(--color-separator)', borderRadius: 999, background: 'transparent',
              color: 'var(--color-text-secondary)', padding: '6px 9px', fontSize: 10.5,
              cursor: findingConnections ? 'wait' : 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {findingConnections ? 'looking…' : 'find connections'}
          </button>
        )}
      </div>
      {(error || refreshError || degraded) && (
        <div style={{ display: 'grid', gap: 6, padding: '0 14px 10px' }}>
          {error && <div role="alert" style={{ fontSize: 11.5, color: 'var(--color-destructive)' }}>{error}</div>}
          {refreshError && <div role="alert" style={{ fontSize: 11.5, color: 'var(--color-destructive)' }}>{refreshError}</div>}
          {!error && degraded && (
            <div role="status" style={{ fontSize: 11.5, color: 'var(--color-text-secondary)' }}>
              Some signals are unavailable: {unavailableSources.join(', ')}.
            </div>
          )}
        </div>
      )}
      {items.length > 0 && <div style={{ borderTop: '1px solid var(--color-separator)' }}>
        {items.map((item, index) => (
          <article
            key={item.id}
            data-testid="kitty-notice"
            style={{
              display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 12,
              alignItems: 'center', padding: '11px 14px',
              borderTop: index === 0 ? 'none' : '1px solid var(--color-separator)',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 9.5, fontWeight: 750, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
                {sourceLabel[item.source] ?? item.source}
              </div>
              <div style={{ marginTop: 3, fontSize: 13.5, fontWeight: 720, color: 'var(--color-text-primary)', lineHeight: 1.25 }}>{item.title}</div>
              <div style={{ marginTop: 3, fontSize: 11.5, color: 'var(--color-text-secondary)', lineHeight: 1.35 }}>{item.detail}</div>
            </div>
            {item.project_id != null && onOpenProject ? (
              <button
                type="button"
                aria-label={`Open project for ${item.title}`}
                onClick={() => onOpenProject(item.project_id as number)}
                style={actionStyle}
              >
                open
              </button>
            ) : onDiscuss ? (
              <button
                type="button"
                aria-label={`Talk to Kitty about ${item.title}`}
                onClick={() => onDiscuss(item.prompt)}
                style={actionStyle}
              >
                discuss
              </button>
            ) : null}
          </article>
        ))}
      </div>}
    </section>
  )
}

export function filterIntelligenceProjection(
  projection: GatewayIntelligenceProjection | undefined,
  visibleTiles: Record<string, boolean>,
): GatewayIntelligenceProjection | undefined {
  if (!projection) return projection
  const visible = projection.items.filter((item) => {
    if (item.source === 'deadline') return visibleTiles.deadlines !== false
    if (item.source === 'insight') return visibleTiles['insight-loop'] !== false
    if (item.source === 'life') return visibleTiles.today !== false
    return true
  })
  return {
    ...projection,
    items: visible,
    counts: { ...projection.counts, shown: Math.min(visible.length, 3) },
  }
}

const actionStyle: React.CSSProperties = {
  border: 'none', borderRadius: 8, background: 'var(--color-surface-elevated)',
  color: 'var(--color-accent)', padding: '7px 9px', fontSize: 10.5, fontWeight: 700,
  cursor: 'pointer', minHeight: 32,
}
