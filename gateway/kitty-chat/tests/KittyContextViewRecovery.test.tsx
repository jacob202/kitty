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
  useProviders: () => query({ active: 'auto', order: [], providers: [], warnings: [], config_path: 'test' }),
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
      {kitty.viewPersistenceWarning && <span role="status">{kitty.viewPersistenceWarning}</span>}
      <button type="button" onClick={() => kitty.setActiveView('builder')}>open builder</button>
      <button type="button" onClick={() => kitty.setActiveView('builder-details')}>open builder details</button>
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
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('surfaces a warning when the selected view cannot be persisted for reload', async () => {
    const originalSetItem = window.localStorage.setItem.bind(window.localStorage)
    vi.spyOn(window.localStorage, 'setItem').mockImplementation((key: string, value: string) => {
      if (key === 'kitty-active-view') throw new DOMException('storage denied')
      originalSetItem(key, value)
    })
    mountHarness()
    await waitFor(() => expect(screen.getByTestId('active-view')).toHaveTextContent('chat'))

    act(() => screen.getByRole('button', { name: 'open builder' }).click())

    expect(screen.getByTestId('active-view')).toHaveTextContent('work')
    expect(screen.getByRole('status')).toHaveTextContent('This view cannot be remembered for reload because browser storage is unavailable.')
  })

  it('allows the secondary Builder details surface without changing ordinary Builder routing', async () => {
    mountHarness()
    await waitFor(() => expect(screen.getByTestId('active-view')).toHaveTextContent('chat'))

    act(() => screen.getByRole('button', { name: 'open builder details' }).click())
    expect(screen.getByTestId('active-view')).toHaveTextContent('builder-details')
  })

  it('surfaces a warning when remembered-view storage cannot be read on reload', async () => {
    const originalGetItem = window.localStorage.getItem.bind(window.localStorage)
    vi.spyOn(window.localStorage, 'getItem').mockImplementation((key: string) => {
      if (key === 'kitty-active-view') throw new DOMException('storage denied')
      return originalGetItem(key)
    })

    mountHarness()

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(
      'This view cannot be remembered for reload because browser storage is unavailable.',
    ))
    expect(screen.getByTestId('active-view')).toHaveTextContent('chat')
  })

  it('restores canonical Work after reload instead of falling back to Chat', async () => {
    const first = mountHarness()
    await waitFor(() => expect(screen.getByTestId('active-view')).toHaveTextContent('chat'))

    act(() => screen.getByRole('button', { name: 'open builder' }).click())
    expect(screen.getByTestId('active-view')).toHaveTextContent('work')

    first.unmount()
    mountHarness()

    await waitFor(() => expect(screen.getByTestId('active-view')).toHaveTextContent('work'))
  })
})
