import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { KittyProvider, useKitty } from '../src/state/KittyContext'

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))

const query = (data: unknown = undefined) => ({
  data,
  isFetched: true,
  isSuccess: false,
  isLoading: false,
  isPending: false,
  isError: false,
  error: null,
})

vi.mock('../src/lib/queries', () => ({
  useGatewayBrief: () => query({ fromLiveGateway: true }),
  useGatewayModels: () => query({ models: [], fromLiveGateway: false }),
  useGatewayRuntimeManifest: () => query(),
  useActiveProject: () => query({ project: null }),
  useProjects: () => query([]),
  useSetActiveProject: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useLoops: () => query({ loops: [] }),
  useInsights: () => query({ insights: [] }),
  usePrompts: () => query([]),
  useToggleLoop: () => ({ mutate: vi.fn() }),
  useDismissInsight: () => ({ mutate: vi.fn() }),
  hasActiveBuilderRun: () => false,
}))

vi.mock('../src/hooks/useKittyState', () => ({ useKittyState: () => 'idle' }))
vi.mock('../src/lib/pwa', () => ({
  usePwaInstall: () => ({ state: 'unsupported', error: null, installing: false, install: vi.fn() }),
}))

function Harness() {
  const kitty = useKitty()
  return (
    <div>
      <span data-testid="active-view">{kitty.activeView}</span>
      <button type="button" onClick={() => kitty.setActiveView('builder')}>open builder</button>
    </div>
  )
}

function mountHarness() {
  return render(<KittyProvider><Harness /></KittyProvider>)
}

describe('Kitty active view recovery', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem('kitty-onboarded', 'true')
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ chats: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('restores canonical Work after reload instead of falling back to Home', async () => {
    const first = mountHarness()
    await waitFor(() => expect(screen.getByTestId('active-view')).toHaveTextContent('home'))

    act(() => screen.getByRole('button', { name: 'open builder' }).click())
    expect(screen.getByTestId('active-view')).toHaveTextContent('work')

    first.unmount()
    mountHarness()

    await waitFor(() => expect(screen.getByTestId('active-view')).toHaveTextContent('work'))
  })
})
