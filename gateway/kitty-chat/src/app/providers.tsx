'use client'
import { useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider, MutationCache } from '@tanstack/react-query'

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    mutationCache: new MutationCache({
      onError: (error) => {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(
            new CustomEvent('kitty:toast', {
              detail: { message: error.message || 'Action failed', type: 'error' },
            })
          )
        }
      },
    }),
    defaultOptions: {
      queries: {
        // Cache for a minute, refetch on focus so the dashboard recovers
        // when the gateway comes back without a hard refresh.
        staleTime: 60_000,
        refetchOnWindowFocus: true,
        retry: 2,
        retryDelay: attempt => Math.min(1000 * 2 ** attempt, 8000),
      },
    },
  }))
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
