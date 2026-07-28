'use client'
import { HomeState } from '@/components/HomeState'
import { KittyThread } from '@/components/KittyThread'

export default function HomeView({ compact, preferredName, onDecideInChat, onNavigate, onExpertClick, chatProps }: any) {
  if (chatProps?.messages?.length > 0) {
    return <KittyThread {...chatProps} compact={compact} />
  }
  return (
    <HomeState
      compact={compact}
      preferredName={preferredName}
      onDecideInChat={onDecideInChat}
      onNavigate={onNavigate}
      onExpertClick={onExpertClick}
    />
  )
}
