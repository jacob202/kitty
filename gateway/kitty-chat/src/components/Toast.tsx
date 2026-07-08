'use client'
import { useEffect, useState } from 'react'

export interface Toast {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

let toastIdCounter = 0

export function ToastManager() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    // Listen for custom kitty:unauthorized event
    const handleAuthError = () => {
      addToast('Session expired or unauthorized. Please re-authenticate.', 'error')
    }

    // Global promise rejection handler for unhandled fetch failures
    const handleRejection = (event: PromiseRejectionEvent) => {
      const msg = event.reason?.message || String(event.reason)
      if (msg && msg !== 'AbortError') {
        addToast(msg, 'error')
      }
    }

    // Listen for custom toast events from anywhere in the app
    const handleCustomToast = (e: CustomEvent<Omit<Toast, 'id'>>) => {
      addToast(e.detail.message, e.detail.type)
    }

    window.addEventListener('kitty:unauthorized', handleAuthError as EventListener)
    window.addEventListener('kitty:toast', handleCustomToast as EventListener)
    window.addEventListener('unhandledrejection', handleRejection)

    return () => {
      window.removeEventListener('kitty:unauthorized', handleAuthError as EventListener)
      window.removeEventListener('kitty:toast', handleCustomToast as EventListener)
      window.removeEventListener('unhandledrejection', handleRejection)
    }
  }, [])

  function addToast(message: string, type: Toast['type']) {
    const id = ++toastIdCounter
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }

  if (toasts.length === 0) return null

  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      zIndex: 9999,
      maxWidth: 320,
    }}>
      {toasts.map(toast => (
        <div key={toast.id} style={{
          background: toast.type === 'error' ? 'var(--c-red)' : toast.type === 'success' ? 'var(--c-green)' : 'var(--surface-2)',
          color: toast.type === 'info' ? 'var(--ink)' : 'var(--bg)',
          padding: '12px 16px',
          borderRadius: 8,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          fontFamily: 'var(--font-body)',
          fontSize: 14,
          fontWeight: 500,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          animation: 'slideIn 0.2s ease-out',
        }}>
          <span>{toast.message}</span>
          <button
            onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              opacity: 0.8,
              fontSize: 16,
              marginLeft: 12
            }}
          >
            ×
          </button>
        </div>
      ))}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideIn {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}} />
    </div>
  )
}
