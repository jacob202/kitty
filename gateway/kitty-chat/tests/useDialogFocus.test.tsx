import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { useDialogFocus } from '../src/hooks/useDialogFocus'

function Harness() {
  const [open, setOpen] = useState(false)
  const dialogRef = useDialogFocus({ open, onClose: () => setOpen(false) })
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open panel</button>
      {open && (
        <section ref={dialogRef} role="dialog" aria-label="Test panel">
          <button type="button">First</button>
          <button type="button">Last</button>
          <button type="button" onClick={() => setOpen(false)}>Close</button>
        </section>
      )}
    </>
  )
}

function SuspendedHarness({ onClose }: { onClose: () => void }) {
  const dialogRef = useDialogFocus({ open: true, enabled: false, onClose })
  return <section ref={dialogRef} role="dialog" aria-label="Parent panel"><button type="button">Parent control</button></section>
}

describe('useDialogFocus', () => {
  it('can suspend keyboard trapping while a nested dialog is active', () => {
    const onClose = vi.fn()
    render(<SuspendedHarness onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('moves focus inside, traps Tab, closes on Escape, and restores the trigger', () => {
    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'Open panel' })
    trigger.focus()
    fireEvent.click(trigger)

    const first = screen.getByRole('button', { name: 'First' })
    const close = screen.getByRole('button', { name: 'Close' })
    expect(first).toHaveFocus()

    close.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(first).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(close).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Test panel' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
