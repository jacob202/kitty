'use client'
import type { ReactNode, CSSProperties } from 'react'
import { X } from 'lucide-react'

export interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  width?: number | string
}

export function Dialog({ open, onClose, title, children, width = 420 }: DialogProps) {
  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.6)',
        padding: 16,
      }}
    >
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          borderRadius: 16,
          maxWidth: width,
          width: '100%',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow)',
        }}
      >
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px',
          borderBottom: '1px solid var(--line)',
        }}>
          <h2 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--ink)',
            margin: 0,
          }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={closeBtnStyle}
          >
            <X size={18} />
          </button>
        </div>
        <div style={{ overflowY: 'auto', padding: '14px 18px', flex: 1 }}>
          {children}
        </div>
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
  if (!open) return null

  const isLeft = side === 'left'

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
        background: 'rgba(0,0,0,0.4)',
      }}
    >
      <div style={{
        position: 'fixed',
        top: 0,
        bottom: 0,
        [isLeft ? 'left' : 'right']: 0,
        width: 'min(85vw, 360px)',
        background: 'var(--surface)',
        borderLeft: isLeft ? 'none' : '1px solid var(--line)',
        borderRight: isLeft ? '1px solid var(--line)' : 'none',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: 'var(--shadow)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 16px',
          borderBottom: '1px solid var(--line)',
        }}>
          <h2 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--ink)',
            margin: 0,
          }}>
            {title}
          </h2>
          <button onClick={onClose} aria-label="Close" style={closeBtnStyle}>
            <X size={18} />
          </button>
        </div>
        <div style={{ overflowY: 'auto', flex: 1, padding: 12 }}>
          {children}
        </div>
      </div>
    </div>
  )
}

export { Sheet }

const closeBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--ink-2)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 36,
  height: 36,
  borderRadius: 8,
}
