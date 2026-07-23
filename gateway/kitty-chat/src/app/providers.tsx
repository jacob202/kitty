'use client'
import { useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from '@/components/Toast'

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: true,
        retry: 2,
        retryDelay: attempt => Math.min(1000 * 2 ** attempt, 8000),
      },
    },
  }))
  return <QueryClientProvider client={client}><ToastProvider>{children}</ToastProvider></QueryClientProvider>
}
