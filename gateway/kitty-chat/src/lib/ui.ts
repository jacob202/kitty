import type { CSSProperties } from 'react'

// Canonical visual language for dashboard cards.
// One card surface, one accent (--primary), tight type scale.

/** Outer card / panel container. */
export const card: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: 16,
}

/** Header row inside a card: title left, count/meta right, hairline underneath.
 *  Containers using this should rely on their own column `gap` for spacing
 *  between the header and the body. */
export const cardHeader: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingBottom: 12,
  borderBottom: '1px solid var(--border-dim)',
}

export const cardTitle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
  letterSpacing: '-0.01em',
}

/** Small monospace meta/count, e.g. "3 items". */
export const cardMeta: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 600,
  color: 'var(--text-muted)',
  letterSpacing: '0.04em',
}

/** Uppercase section label used between cards / above lists. */
export const sectionLabel: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
}

/** Recessed inner item sitting inside a card. */
export const itemCard: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '12px 14px',
  transition: 'background 0.15s ease, border-color 0.15s ease',
}

export const bodyText: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  color: 'var(--text-dim)',
  lineHeight: 1.5,
}

/** Calm empty state — no italics, low emphasis. */
export const emptyState: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-faint)',
  textAlign: 'center',
  padding: '20px 0',
}

export const ACCENT = 'var(--primary)'
