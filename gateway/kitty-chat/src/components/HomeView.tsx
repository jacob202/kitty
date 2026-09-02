'use client'
import { HomeState } from '@/components/HomeState'

export default function HomeView({ compact, preferredName, onDecideInChat, onNavigate, onExpertClick, onOpenProject, onPromptSelect }: any) {
  return (
    <HomeState
      compact={compact}
      preferredName={preferredName}
      onDecideInChat={onDecideInChat}
      onNavigate={onNavigate}
      onExpertClick={onExpertClick}
      onOpenProject={onOpenProject}
      onPromptSelect={onPromptSelect}
    />
  )
}
