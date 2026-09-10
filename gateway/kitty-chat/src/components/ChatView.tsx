'use client'
import { KittyThread } from '@/components/KittyThread'
import { Model } from '@/lib/types'

export default function ChatView({ compact = false, ...props }: {
  compact?: boolean
  messages: any[]
  chatId: string
  isStreaming: boolean
  catState: any
  onRetry: () => void
  retryBranches?: Record<number, any[][]>
  onSwitchBranch?: (messageIndex: number, branchIndex: number) => void
  onStartClick: () => void
  onChipClick: (chip: string) => void
  onOpenWork?: () => void
  models?: Model[]
  overrideModel?: Model | null
  onOverrideModel?: (m: Model | null) => void
}): React.ReactElement {
  return <KittyThread {...props} compact={compact} />
}
