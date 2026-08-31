import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'

import { InputBar } from '../src/components/InputBar'
import type { ContextReference } from '../src/lib/context-references'

const candidates = [
  { kind: 'project' as const, id: '7', label: 'kitty', description: 'Project · active' },
  { kind: 'artifact' as const, id: 'artifact_1', label: 'research-report.md', description: 'Artifact · Markdown' },
  { kind: 'chat' as const, id: 'chat-9', label: 'Earlier design discussion', description: 'Conversation' },
]

function Harness({ onSend = vi.fn() }: { onSend?: () => void }) {
  const [value, setValue] = useState('')
  const [refs, setRefs] = useState<ContextReference[]>([])
  return (
    <InputBar
      value={value}
      onChange={setValue}
      onSend={onSend}
      contextCandidates={candidates}
      contextRefs={refs}
      onAddContextRef={(ref) => setRefs((current) => [...current, ref])}
      onRemoveContextRef={(kind, id) => setRefs((current) => current.filter((ref) => ref.kind !== kind || ref.id !== id))}
    />
  )
}

describe('InputBar @ context picker', () => {
  afterEach(cleanup)

  it('finds durable objects after @ and inserts the human label', () => {
    render(<Harness />)
    const textarea = screen.getByRole('textbox', { name: 'Message Kitty' })

    fireEvent.change(textarea, { target: { value: 'Compare @ki' } })

    expect(screen.getByRole('listbox', { name: 'Context suggestions' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('option', { name: /kitty.*Project/i }))
    expect(textarea).toHaveValue('Compare @kitty ')
    expect(screen.getByText('kitty')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove context kitty' })).toBeInTheDocument()
  })

  it('uses Enter to select a context result instead of sending the message', () => {
    const onSend = vi.fn()
    render(<Harness onSend={onSend} />)
    const textarea = screen.getByRole('textbox', { name: 'Message Kitty' })

    fireEvent.change(textarea, { target: { value: 'Use @research' } })
    fireEvent.keyDown(textarea, { key: 'Enter' })

    expect(onSend).not.toHaveBeenCalled()
    expect(textarea).toHaveValue('Use @research-report.md ')
    expect(screen.getByRole('button', { name: 'Remove context research-report.md' })).toBeInTheDocument()
  })

  it('removes a selected context chip without changing the typed prompt', () => {
    render(<Harness />)
    const textarea = screen.getByRole('textbox', { name: 'Message Kitty' })
    fireEvent.change(textarea, { target: { value: '@ki' } })
    fireEvent.click(screen.getByRole('option', { name: /kitty.*Project/i }))

    fireEvent.click(screen.getByRole('button', { name: 'Remove context kitty' }))

    expect(textarea).toHaveValue('@kitty ')
    expect(screen.queryByRole('button', { name: 'Remove context kitty' })).not.toBeInTheDocument()
  })
})
