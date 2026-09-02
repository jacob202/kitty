'use client'
import type { ReactNode, CSSProperties } from 'react'
import { X } from 'lucide-react'

import { useDialogFocus } from '@/hooks/useDialogFocus'

export interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  width?: number | string
}

export function Dialog({ open, onClose, title, children, width = 420 }: DialogProps) {
  const dialogRef = useDialogFocus<HTMLDivElement>({ open, onClose })
  if (!open) return null

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={backdropStyle}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ ...dialogStyle, maxWidth: width }}
      >
        <div style={headerStyle}>
          <h2 style={titleStyle}>{title}</h2>
          <button onClick={onClose} aria-label="Close" style={closeBtnStyle}>
            <X size={18} />
          </button>
        </div>
        <div style={dialogBodyStyle}>{children}</div>
      </div>
    </div>
  )
}

function Sheet({ open, onClose, title, children, side = 'right' }: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  side?: 'left' | 'right'
}) {
  const dialogRef = useDialogFocus<HTMLDivElement>({ open, onClose })
  if (!open) return null

  const isLeft = side === 'left'

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={{ ...backdropStyle, justifyContent: isLeft ? 'flex-start' : 'flex-end', alignItems: 'stretch' }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ ...sheetStyle, borderLeft: isLeft ? 'none' : '1px solid var(--line)', borderRight: isLeft ? '1px solid var(--line)' : 'none' }}
      >
        <div style={headerStyle}>
          <h2 style={titleStyle}>{title}</h2>
          <button onClick={onClose} aria-label="Close" style={closeBtnStyle}>
            <X size={18} />
          </button>
        </div>
        <div style={sheetBodyStyle}>{children}</div>
      </div>
    </div>
  )
}

export { Sheet }

const backdropStyle: CSSProperties = {
  position: 'fixed',
  inset: 0,
  zIndex: 200,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--overlay-backdrop)',
  padding: 16,
}

const dialogStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  borderRadius: 'var(--r-surface)',
  width: '100%',
  maxHeight: '85vh',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: 'var(--shadow-overlay)',
}

const sheetStyle: CSSProperties = {
  width: 'min(88vw, 400px)',
  height: '100%',
  background: 'var(--surface)',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: 'var(--shadow-overlay)',
}

const headerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 16,
  minHeight: 64,
  padding: '10px 14px 10px 18px',
  borderBottom: '1px solid var(--line)',
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--ink)',
  margin: 0,
}

const dialogBodyStyle: CSSProperties = { overflowY: 'auto', padding: '16px 18px 18px', flex: 1 }
const sheetBodyStyle: CSSProperties = { overflowY: 'auto', flex: 1, padding: 14 }

const closeBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--ink-2)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 44,
  height: 44,
  borderRadius: 'var(--r-control)',
  flexShrink: 0,
}
