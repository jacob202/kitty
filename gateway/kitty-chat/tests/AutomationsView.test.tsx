import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AutomationsView from '../src/components/AutomationsView'

vi.mock('../src/components/CronPanel', () => ({
  CronPanel: ({ variant }: { variant?: string }) => <div>schedule manager {variant}</div>,
}))
vi.mock('../src/components/LoopWatch', () => ({
  LoopWatch: ({ title }: { title?: string }) => <div>{title}</div>,
}))
vi.mock('../src/components/MonitorPanel', () => ({
  MonitorPanel: () => <div>monitor manager</div>,
}))

afterEach(cleanup)

describe('AutomationsView', () => {
  it('presents schedules and background routines as one product surface', () => {
    render(
      <AutomationsView
        isMobile={false}
        loops={[]}
        loopsLoading={false}
        onLoopToggle={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Automations' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Schedules' })).toBeVisible()
    expect(screen.getByText('schedule manager full')).toBeVisible()
    expect(screen.getByText('Background routines')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Monitors' })).toBeVisible()
    expect(screen.getByText('monitor manager')).toBeVisible()
  })
})

describe('AutomationsView async truth', () => {
  afterEach(cleanup)

  it('shows a routine error instead of an empty routine list', () => {
    render(
      <AutomationsView
        isMobile={false}
        loops={[]}
        loopsLoading={false}
        loopsError="Gateway unavailable"
        onLoopToggle={vi.fn()}
      />,
    )

    expect(screen.getByText(/background routines are unavailable right now/i)).toBeVisible()
    expect(screen.queryByText(/no loops configured/i)).not.toBeInTheDocument()
  })
})
