import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useUploadCapture } from '../src/lib/queries'

describe('capture artifact invalidation', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('refreshes canonical artifacts as soon as a captured file is accepted', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      artifact_id: 'artifact_1', status: 'queued', message: 'queued',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useUploadCapture(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync(new File(['hello'], 'capture.txt', { type: 'text/plain' }))
    })

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['knowledge', 'sources'] })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['artifacts'] })
  })
})
