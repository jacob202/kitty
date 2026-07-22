'use client'

import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useKittyRuntime, type KittyRuntimeOptions } from '@/lib/kitty-runtime'

interface Props extends KittyRuntimeOptions {
  children: React.ReactNode
}

export function KittyRuntimeProvider({ children, ...runtimeOptions }: Props) {
  const runtime = useKittyRuntime(runtimeOptions)
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
