import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const handleNewChat = vi.fn()
const setActiveView = vi.fn()

vi.mock('../src/state/KittyContext', () => ({
  useKitty: () => ({ handleNewChat, setActiveView }),
}))

vi.mock('../src/components/ProjectsPanel', () => ({
  ProjectsPanel: ({ onNavigate, onStartChat }: {
    onNavigate: (view: string) => void
    onStartChat: () => void
  }) => (
    <button
      type="button"
      onClick={() => {
        onStartChat()
        onNavigate('chat')
      }}
    >
      start project chat
    </button>
  ),
}))

import ProjectsView from '../src/components/ProjectsView'

beforeEach(() => {
  handleNewChat.mockReset()
  setActiveView.mockReset()
})

afterEach(cleanup)

describe('ProjectsView', () => {
  it('wires Project Workspace chat continuation to a fresh chat', () => {
    render(<ProjectsView isMobile={false} />)

    fireEvent.click(screen.getByRole('button', { name: /start project chat/i }))

    expect(handleNewChat).toHaveBeenCalledTimes(1)
    expect(setActiveView).toHaveBeenCalledWith('chat')
  })
})
