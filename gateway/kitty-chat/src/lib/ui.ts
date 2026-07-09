import type { CSSProperties } from 'react'

// Canonical visual language for dashboard cards.
// One card surface, one accent (--primary), tight type scale.

/** True when the cosmic (dark cockpit) theme is active. */
function isCosmic(): boolean {
  if (typeof document === 'undefined') return false
  return document.documentElement.getAttribute('data-theme') === 'cosmic'
}

/** Glass treatment layered onto card/itemCard under the cosmic theme. */
const glassExtras = (): CSSProperties =>
  isCosmic()
    ? {
        background: 'rgba(20, 28, 48, 0.55)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        border: '1px solid rgba(196, 132, 76, 0.28)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45)',
      }
    : {}

/** Outer card / panel container. */
export const card: CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: 16,
  ...glassExtras(),
}

/** Header row inside a card: title left, count/meta right, hairline underneath.
 *  Containers using this should rely on their own column `gap` for spacing
 *  between the header and the body. */
export const cardHeader: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingBottom: 12,
  borderBottom: '1px solid var(--line)',
}

export const cardTitle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--ink)',
  letterSpacing: '-0.01em',
}

/** Small monospace meta/count, e.g. "3 items". */
export const cardMeta: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 600,
  color: 'var(--ink-2)',
  letterSpacing: '0.04em',
}

/** Uppercase section label used between cards / above lists. */
export const sectionLabel: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.12em',
  textTransform: 'lowercase',
  color: 'var(--ink-2)',
}

/** Recessed inner item sitting inside a card. */
export const itemCard: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '12px 14px',
  transition: 'background 0.15s ease, border-color 0.15s ease',
  ...(isCosmic()
    ? {
        background: 'rgba(28, 38, 64, 0.72)',
        border: '1px solid rgba(196, 132, 76, 0.20)',
      }
    : {}),
}

export const bodyText: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--ink-2)',
  lineHeight: 1.5,
}

/** Calm empty state — no italics, low emphasis. */
export const emptyState: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  textAlign: 'center',
  padding: '20px 0',
}

export const ACCENT = 'var(--primary)'
