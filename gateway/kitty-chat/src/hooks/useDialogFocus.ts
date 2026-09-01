'use client'

import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    .filter(element => element.getAttribute('aria-hidden') !== 'true')
}

export function useDialogFocus<T extends HTMLElement = HTMLElement>({ open, enabled = open, onClose }: {
  open: boolean
  enabled?: boolean
  onClose: () => void
}): RefObject<T | null> {
  const dialogRef = useRef<T | null>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const dialog = dialogRef.current
    if (!dialog) return

    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null
    const initialTarget = focusableElements(dialog)[0] ?? dialog
    if (initialTarget === dialog && !dialog.hasAttribute('tabindex')) dialog.tabIndex = -1
    initialTarget.focus()

    return () => {
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open || !enabled) return
    const dialog = dialogRef.current
    if (!dialog) return

    const onKeyDown = (event: KeyboardEvent) => {
      const activeModals = Array.from(
        document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]:not([aria-hidden="true"])'),
      )
      if (activeModals.length > 1 && activeModals[activeModals.length - 1] !== dialog) return

      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return

      const focusable = focusableElements(dialog)
      if (focusable.length === 0) {
        event.preventDefault()
        dialog.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      const outside = !(active instanceof Node) || !dialog.contains(active)

      if (event.shiftKey && (active === first || outside)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (active === last || outside)) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [enabled, open])

  return dialogRef
}
