import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useProjectNextSteps } from '../src/lib/queries'
import type { GatewayProject } from '../src/lib/gateway'

const projects: GatewayProject[] = [
  { id: 1, name: 'life', kind: 'life', status: 'active', summary: null, paths: [], last_touched: null, open_questions: [], next_actions: [], links: [] },
  { id: 2, name: 'kitty', kind: 'code', status: 'active', summary: null, paths: [], last_touched: null, open_questions: [], next_actions: [], links: [] },
]

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useProjectNextSteps', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses one bulk next-steps request instead of expected-miss per-project 404 requests', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/projects/next-step-map')) {
        return new Response(JSON.stringify([{ project_id: 1, step: 'Do life thing', why: 'important', recent_win: '', delegable: false, generated_at: 1 }]), { status: 200 })
      }
      const id = url.includes('/projects/1/next') ? 1 : 2
      return new Response(JSON.stringify({ project_id: id, step: `step-${id}`, why: 'why', recent_win: '', delegable: false, generated_at: 1 }), { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useProjectNextSteps(projects), { wrapper })
    await waitFor(() => expect(result.current.every(query => !query.isPending)).toBe(true))

    const urls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(urls).toEqual(['/proxy/projects/next-step-map?project_ids=1%2C2'])
    expect(result.current[0].data?.step).toBe('Do life thing')
    expect(result.current[1].data).toBeNull()
  })
})
