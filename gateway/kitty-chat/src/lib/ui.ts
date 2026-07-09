import type { CSSProperties } from 'react'

// Canonical visual language for the Kitty cockpit.
// The panels are translucent so real data sits inside the starfield instead of
// feeling pasted on top of a separate dashboard.

/** Outer card / panel container. */
export const card: CSSProperties = {
  background: 'linear-gradient(145deg, var(--surface), var(--surface-2))',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 16,
  display: 'grid',
  gap: 12,
  boxShadow: 'var(--shadow-soft)',
  backdropFilter: 'blur(18px)',
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
  gap: 12,
}

export const cardTitle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 15,
  fontWeight: 700,
  color: 'var(--text)',
  letterSpacing: 0,
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
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  color: 'var(--text-muted)',
}

/** Recessed inner item sitting inside a card. */
export const itemCard: CSSProperties = {
  background: 'var(--surface-high)',
  border: '1px solid var(--border-dim)',
  borderRadius: 7,
  padding: '12px 14px',
  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
  transition: 'background 0.15s ease, border-color 0.15s ease, transform 0.15s ease',
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
  textAlign: 'left',
  padding: '20px 0',
}

export const ACCENT = 'var(--primary)'
