'use client'
import { createContext, useContext, useState, useCallback, useRef, type ReactNode, type CSSProperties } from 'react'

type ToastType = 'success' | 'error' | 'info'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface Toast {
  id: number
  message: string
  type: ToastType
  action?: ToastAction  // e.g. { label: 'Undo', onClick: () => revert() }
}

interface ToastContextValue {
  toasts: Toast[]
  showToast: (message: string, type?: ToastType, action?: ToastAction) => void
  dismissToast: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(0)

  const showToast = useCallback((message: string, type: ToastType = 'info', action?: ToastAction) => {
    const id = ++toastId.current
    setToasts((prev) => [...prev, { id, message, type, action }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3000)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, showToast, dismissToast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div style={containerStyle} role="region" aria-live="polite" aria-label="Notifications">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const typeStyles: Record<ToastType, CSSProperties> = {
    success: { background: 'var(--c-green)', color: '#000' },
    error: { background: 'var(--c-red)', color: '#fff' },
    info: { background: 'var(--primary)', color: 'var(--on-primary)' },
  }

  return (
    <div
      style={{
        ...toastStyle,
        ...typeStyles[toast.type],
        animation: 'toastIn 0.25s ease-out',
      }}
    >
      <span style={messageStyle}>{toast.message}</span>
      {toast.action && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            toast.action!.onClick()
            onDismiss(toast.id)
          }}
          style={actionStyle}
        >
          {toast.action.label}
        </button>
      )}
      <span style={dismissStyle} onClick={() => onDismiss(toast.id)}>x</span>
    </div>
  )
}

const containerStyle: CSSProperties = {
  position: 'fixed',
  bottom: 24,
  right: 24,
  zIndex: 100,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  pointerEvents: 'none',
  maxWidth: 360,
}

const toastStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '10px 14px',
  borderRadius: 10,
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 500,
  boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
  pointerEvents: 'auto',
}

const messageStyle: CSSProperties = {
  flex: 1,
  wordBreak: 'break-word',
}

const actionStyle: CSSProperties = {
  background: 'rgba(255,255,255,0.2)',
  border: 'none',
  borderRadius: 6,
  padding: '4px 10px',
  fontSize: 12,
  fontWeight: 700,
  cursor: 'pointer',
  color: 'inherit',
  whiteSpace: 'nowrap',
}

const dismissStyle: CSSProperties = {
  opacity: 0.6,
  fontSize: 14,
  fontWeight: 700,
  lineHeight: 1,
  flexShrink: 0,
  cursor: 'pointer',
}

const globalStyleEl = typeof document !== 'undefined' ? document.getElementById('toast-keyframes') : null
if (!globalStyleEl && typeof document !== 'undefined') {
  const style = document.createElement('style')
  style.id = 'toast-keyframes'
  style.textContent = `
    @keyframes toastIn {
      from { opacity: 0; transform: translateX(100%); }
      to { opacity: 1; transform: translateX(0); }
    }
  `
  document.head.appendChild(style)
}
