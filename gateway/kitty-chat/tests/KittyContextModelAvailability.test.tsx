import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { KittyProvider, useKitty } from '../src/state/KittyContext'

const shared = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  models: null as any,
  runtime: null as any,
  providers: null as any,
}))

const model = (id: string, name: string) => ({ id, name, color: '#fff', glow: '#fff' })
const query = (data: unknown, success = true) => ({
  data, isFetched: true, isSuccess: success, isLoading: false, isPending: false, isError: !success, error: success ? null : new Error('runtime unavailable'),
})

vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => ({ invalidateQueries: shared.invalidateQueries }) }))
vi.mock('../src/lib/queries', () => ({
  useGatewayBrief: () => query({ fromLiveGateway: true }),
  useGatewayModels: () => shared.models,
  useGatewayRuntimeManifest: () => shared.runtime,
  useProviders: () => shared.providers,
  useActiveProject: () => query({ project: null }),
  useProjects: () => query([]),
  useSetActiveProject: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
  useLoops: () => query({ loops: [] }),
  useInsights: () => query({ insights: [] }),
  usePrompts: () => query([]),
  useToggleLoop: () => ({ mutate: vi.fn() }),
  useDismissInsight: () => ({ mutate: vi.fn() }),
  hasActiveBuilderRun: () => false,
}))
vi.mock('../src/hooks/useKittyState', () => ({ useKittyState: () => 'idle' }))
vi.mock('../src/lib/pwa', () => ({ usePwaInstall: () => ({ state: 'unsupported', error: null, installing: false, install: vi.fn() }) }))

function Harness() {
  const k = useKitty()
  return <div>
    <span data-testid="live">{String(k.modelGateway.live)}</span>
    <span data-testid="error">{k.modelGateway.error ?? ''}</span>
    <span data-testid="available">{k.availableModels.map(m => m.id).join(',')}</span>
    <span data-testid="override">{k.overrideModel?.id ?? ''}</span>
    <button onClick={() => k.setOverrideModel(model('kitty-code', 'Code'))}>override code</button>
    <button onClick={k.retryGatewayBootstrap}>retry models</button>
  </div>
}

function runtime(ids: string[]) {
  return query({ inference: { available_models: { state: 'available', value: ids } } })
}

function mount() { return render(<KittyProvider><Harness /></KittyProvider>) }

describe('Kitty model availability reconciliation', () => {
  beforeEach(() => {
    shared.invalidateQueries.mockReset()
    shared.models = query({ models: [model('kitty-default', 'Daily Kitty'), model('kitty-code', 'Code')], fromLiveGateway: true, error: null })
    shared.runtime = runtime(['kitty-default', 'kitty-code'])
    shared.providers = query({ active: 'auto', order: [], providers: [], warnings: [], config_path: 'test' })
    window.localStorage.clear(); window.localStorage.setItem('kitty-onboarded', 'true')
    Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn() })) })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ chats: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
  })
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('retries the runtime manifest together with model discovery', async () => {
    mount()
    fireEvent.click(screen.getByRole('button', { name: 'retry models' }))
    await waitFor(() => expect(shared.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['runtime-manifest'] }))
  })

  it('treats an empty curated/runtime intersection as unavailable with recovery copy', async () => {
    shared.models = query({ models: [model('kitty-code', 'Code')], fromLiveGateway: true, error: null })
    shared.runtime = runtime(['kitty-default'])
    mount()
    await waitFor(() => expect(screen.getByTestId('available')).toHaveTextContent(''))
    expect(screen.getByTestId('live')).toHaveTextContent('false')
    expect(screen.getByTestId('error')).toHaveTextContent(/No live curated models/i)
  })

  it('keeps Daily Kitty sendable through an explicitly selected configured direct provider', async () => {
    shared.models = query({ models: [], fromLiveGateway: false, error: 'Gateway returned 503' })
    shared.runtime = query(undefined, false)
    shared.providers = query({
      active: 'openrouter', order: ['openrouter'], warnings: [], config_path: 'test',
      providers: [{ name: 'openrouter', configured: true, disabled: false }],
    })

    mount()

    await waitFor(() => expect(screen.getByTestId('live')).toHaveTextContent('true'))
    expect(screen.getByTestId('available')).toHaveTextContent('kitty-default')
    expect(screen.getByTestId('error')).toHaveTextContent('')
  })

  it('clears a one-shot override when that route leaves the live shortlist', async () => {
    const view = mount()
    fireEvent.click(screen.getByRole('button', { name: 'override code' }))
    expect(screen.getByTestId('override')).toHaveTextContent('kitty-code')

    shared.models = query({ models: [model('kitty-default', 'Daily Kitty')], fromLiveGateway: true, error: null })
    shared.runtime = runtime(['kitty-default'])
    await act(async () => { view.rerender(<KittyProvider><Harness /></KittyProvider>) })

    await waitFor(() => expect(screen.getByTestId('override')).toHaveTextContent(''))
  })
})
