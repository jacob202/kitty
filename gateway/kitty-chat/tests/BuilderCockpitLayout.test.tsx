import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BuilderCockpit } from '../src/components/builder/BuilderCockpit'
import { OperatorControls } from '../src/components/builder/OperatorControls'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return {
    ...actual,
    useGatewayRuntimeManifest: vi.fn(),
    useOperatorCommand: vi.fn(),
  }
})

vi.mock('../src/components/builder/BuilderPacketTree', () => ({
  BuilderPacketTree: () => <div data-testid="packet-tree">packet tree</div>,
}))
vi.mock('../src/components/builder/BuilderWorkerPane', () => ({
  WorkerPane: () => <div>worker pane</div>,
}))
vi.mock('../src/components/builder/BuilderWorkerInspector', () => ({
  WorkerInspector: () => <div>worker inspector</div>,
}))
const snapshot = {
  initiatives: [
    { initiative_id: 'A', title: 'Active initiative', state: 'active', packets: [] },
    { initiative_id: 'B', title: 'Paused initiative', state: 'paused', packets: [] },
  ],
}

function mockQueries() {
  vi.mocked(queries.useGatewayRuntimeManifest).mockReturnValue({
    data: { execution: { builder: { value: snapshot } } },
    isLoading: false,
    error: null,
  } as never)
  vi.mocked(queries.useOperatorCommand).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as never)
}

describe('Builder cockpit responsive hierarchy', () => {
  beforeEach(mockQueries)
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('renders only the mobile workspace when Kitty is compact', () => {
    render(<BuilderCockpit isMobile onBack={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Builder details' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'packets' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'single' })).not.toBeInTheDocument()
  })

  it('renders only the desktop cockpit when Kitty is wide', () => {
    render(<BuilderCockpit isMobile={false} onBack={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'single' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'packets' })).not.toBeInTheDocument()
  })

  it('keeps global operator actions collapsed until requested', () => {
    render(<OperatorControls snapshot={snapshot as never} selectedPacket={null} />)

    const disclosure = screen.getByText(/global controls/i)
    expect(disclosure).toBeVisible()
    expect(screen.getByRole('button', { name: /pause active initiative/i })).not.toBeVisible()
    expect(screen.getByRole('button', { name: /resume paused initiative/i })).not.toBeVisible()

    fireEvent.click(disclosure)
    expect(screen.getByRole('button', { name: /pause active initiative/i })).toBeVisible()
    expect(screen.getByRole('button', { name: /resume paused initiative/i })).toBeVisible()
  })
})
