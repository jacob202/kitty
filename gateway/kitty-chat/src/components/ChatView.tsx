'use client'
import { KittyThread } from '@/components/KittyThread'

export default function ChatView({ compact, ...props }: any) {
  return <KittyThread {...props} compact={compact} />
}
