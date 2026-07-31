import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import HomeView from '../src/components/HomeView'

vi.mock('../src/components/HomeState', () => ({
  HomeState: () => <div>life-first home</div>,
}))

vi.mock('../src/components/KittyThread', () => ({
  KittyThread: () => <div>active chat thread</div>,
}))

afterEach(cleanup)

describe('HomeView', () => {
  it('shows the home dashboard even when the active chat has messages', () => {
    render(
      <HomeView
        compact={false}
        preferredName="Jacob"
        onDecideInChat={vi.fn()}
        onNavigate={vi.fn()}
        onExpertClick={vi.fn()}
        chatProps={{ messages: [{ id: 'message-1', content: 'hello' }] }}
      />,
    )

    expect(screen.getByText('life-first home')).toBeInTheDocument()
    expect(screen.queryByText('active chat thread')).not.toBeInTheDocument()
  })
})
