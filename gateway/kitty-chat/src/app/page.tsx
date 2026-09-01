'use client'
import { useState } from 'react'
import { useKitty } from '@/state/KittyContext'
import { TopBar } from '@/components/TopBar'
import { ThreadGoal } from '@/components/ThreadGoal'
import { SignalFeed } from '@/components/SignalCard'
import { InputBar } from '@/components/InputBar'
import { Rail } from '@/components/Rail'
import { BottomNav } from '@/components/BottomNav'
import { SessionSidebar } from '@/components/SessionSidebar'
import { OnboardingModal } from '@/components/OnboardingModal'
import { CommandPalette } from '@/components/CommandPalette'
import { ActivityCenter } from '@/components/activity/ActivityCenter'
import { KittyRuntimeProvider } from '@/components/KittyRuntimeProvider'
import { ViewRenderer } from '@/components/ViewRenderer'
import { StatusBar } from '@/components/StatusBar'
import { WobFilters, PaperGrain } from '@/components/WobFilters'
import { CatCorner } from '@/components/CrayonCat'
import { composeSkillLaunchInput } from '@/lib/capability-launch'
import { useActivity } from '@/lib/queries'

export default function KittyChat() {
  const k = useKitty()
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)
  const [activityOpen, setActivityOpen] = useState(false)
  const [selectedAgentSessionId, setSelectedAgentSessionId] = useState<number | null>(null)
  const [selectedAutomationRunId, setSelectedAutomationRunId] = useState<string | null>(null)
  const activity = useActivity()
  const activityAttentionCount = (activity.data?.counts.waiting ?? 0) + (activity.data?.counts.failed ?? 0)
  const activityIncomplete = Boolean(activity.error) || Object.values(activity.data?.sources ?? {}).some(source => source.state === 'unavailable')
  const modelUnavailable = !k.modelGateway.live || k.availableModels.length === 0

  return (
    <div
      style={{
        display: 'flex', height: '100dvh', width: '100vw', overflow: 'hidden',
        position: 'relative', background: 'var(--bg)', color: 'var(--ink)',
        fontFamily: 'var(--font-body)',
      }}
    >
      <WobFilters />

      {k.showOnboarding && (
        <OnboardingModal
          onComplete={({ theme: selectedTheme }) => {
            k.setTheme(selectedTheme)
            k.setPreferredName(window.localStorage.getItem('kitty-preferred-name') ?? '')
            document.documentElement.setAttribute('data-theme', selectedTheme)
            k.setShowOnboarding(false)
          }}
        />
      )}

      {!k.isMobile && <Rail activeView={k.activeView} onViewChange={k.setActiveView} theme={k.theme} onToggleTheme={k.handleToggleTheme} />}
      {k.isMobile && <BottomNav activeView={k.activeView} onViewChange={k.setActiveView} />}

      {!k.isMobile && k.activeView === 'chat' && (
        <SessionSidebar
          chats={k.chats} activeChatId={k.activeChatId}
          onSelectChat={k.handleSelectChat} onNewChat={() => { k.handleNewChat(); k.setActiveView('chat') }}
          onCloseChat={k.handleCloseChat} onTogglePin={k.handleTogglePin} collapsed={k.sidebarCollapsed}
        />
      )}

      {k.isMobile && k.mobileSidebarOpen && k.activeView === 'chat' && (
        <>
          <div onClick={() => k.setMobileSidebarOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.6)', zIndex: 40 }} />
          <div
            data-testid="mobile-chat-drawer"
            style={{
              position: 'fixed', inset: '0 auto 0 0', width: 'min(320px, 84vw)',
              height: '100dvh', zIndex: 50, boxShadow: 'var(--shadow)',
              background: 'var(--surface-solid)',
            }}
          >
            <SessionSidebar
              chats={k.chats} activeChatId={k.activeChatId}
              onSelectChat={k.handleSelectChat}
              onNewChat={() => { k.handleNewChat(); k.setActiveView('chat'); if (k.isMobile) k.setMobileSidebarOpen(false) }}
              onCloseChat={k.handleCloseChat} onTogglePin={k.handleTogglePin} collapsed={false} width="min(320px, 84vw)"
            />
          </div>
        </>
      )}

      <KittyRuntimeProvider
        messages={k.activeChat?.messages ?? []} isStreaming={k.isStreaming}
        activeModel={k.activeModel} onSend={(text) => { if (!modelUnavailable) k.handleRuntimeSend(text) }}
        onCancel={k.handleStop} onReload={() => { if (!modelUnavailable) k.handleRetry() }}
      >
        <main style={{
          flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column',
          minHeight: 0, overflow: 'hidden', background: 'var(--bg)',
          ...(k.isMobile ? { paddingBottom: 'var(--bottom-nav-height)' } : {}),
        }}>
          <TopBar
            activeModel={k.activeModel} models={k.availableModels} onSelectModel={k.handleSelectModel}
            isStreaming={k.isStreaming} modelFromGateway={k.modelGateway.live}
            activeView={k.activeView} onViewChange={k.setActiveView}
            kittyMode="default" onKittyModeChange={() => {}}
            sidebarCollapsed={k.sidebarCollapsed} onToggleSidebar={k.handleToggleSidebar}
            isMobile={k.isMobile} catState={k.catState}
            activeProject={k.activeProject} projects={k.projects} onSelectProject={k.handleSelectProject}
            projectLoading={k.projectsQuery.isLoading || k.activeProjectQuery.isLoading}
            projectBusy={k.setActiveProject.isPending}
            runtimeState={k.runtimeQuery.data?.connections.gateway.state ?? 'unknown'}
            runtimeDetail={k.runtimeQuery.data?.connections.gateway.reason ?? (k.runtimeQuery.error instanceof Error ? k.runtimeQuery.error.message : undefined)}
            onCommandPalette={() => setCmdPaletteOpen(true)}
            onActivity={() => setActivityOpen(true)}
            activityAttentionCount={activityAttentionCount}
            activityIncomplete={activityIncomplete}
          />

          {k.activeView === 'chat' && !k.isMobile && (
            <ThreadGoal chat={k.activeChat} compact={k.isMobile} onObjectiveSaved={k.handleObjectiveSaved} onEnsurePersisted={k.persistChat} />
          )}
          {k.activeView === 'chat' && !k.isMobile && <SignalFeed compact={k.isMobile} />}

          {k.viewPersistenceWarning && (
            <div role="status" style={{ padding: '8px 16px', borderBottom: '1px solid var(--line)', color: 'var(--c-yellow)', fontSize: 12 }}>
              {k.viewPersistenceWarning}
            </div>
          )}

          <StatusBar
            showChatSignals={k.activeView === 'chat' || k.activeView === 'home'}
            attachmentErrors={k.attachmentErrors}
            modelUnavailable={k.modelGateway.loaded && modelUnavailable}
            modelError={k.modelGateway.error}
            onRetryModels={k.retryGatewayBootstrap}
            saveState={k.saveState} onRetrySave={k.handleRetrySave}
            briefUnavailable={k.modelGateway.loaded && k.modelGateway.live && k.briefGateway.loaded && !k.briefGateway.live}
            briefError={k.briefGateway.error}
            pwaState={k.pwaInstall.state} pwaError={k.pwaInstall.error}
            pwaInstalling={k.pwaInstall.installing} onPwaInstall={() => void k.pwaInstall.install().catch(console.error)}
          />

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <ViewRenderer
              view={k.activeView}
              compact={k.isMobile}
              theme={k.theme}
              onToggleTheme={k.handleToggleTheme}
              chatProps={{
                messages: k.activeChat?.messages ?? [],
                chatId: k.activeChat?.id ?? '',
                isStreaming: k.isStreaming,
                catState: k.catState,
                onRetry: () => { if (!modelUnavailable) k.handleRetry() },
                retryBranches: k.activeChat?.retryBranches,
                onSwitchBranch: k.handleSwitchBranch,
                onStartClick: () => k.textareaRef.current?.focus(),
                onChipClick: (chip: string) => { k.setInput(chip); k.textareaRef.current?.focus() },
              }}
              homeProps={{
                preferredName: k.preferredName,
                onDecideInChat: k.handleDecideInChat,
                onNavigate: k.setActiveView,
                onExpertClick: (expert: any) => { k.handleNewExpertChat(expert); k.setActiveView('chat') },
              }}
              builderProps={{ onBack: () => k.setActiveView('work') }}
              selectedAgentSessionId={selectedAgentSessionId}
              automationProps={{ selectedRunId: selectedAutomationRunId }}
              toolsProps={{
                loops: k.loops, insights: k.insights, promptTemplates: k.promptTemplates,
                onLoopToggle: k.handleLoopToggle, onInsightDismiss: k.handleInsightDismiss,
                onInsightAction: k.handleInsightAction, onPromptSelect: k.handlePromptSelect,
                loopsLoading: k.loopsQuery.isLoading, loopsError: k.loopsQuery.isError ? (k.loopsQuery.error instanceof Error ? k.loopsQuery.error.message : 'Gateway request failed') : null, insightsLoading: k.insightsQuery.isLoading,
                promptsLoading: k.promptsQuery.isLoading,
              }}
            />
          </div>

          {k.activeView === 'chat' && (
            <InputBar
              value={k.input}
              onChange={(v: string) => { k.setInput(v); if (k.attachmentErrors.length) k.setAttachments([]) }}
              onSend={() => { if (!modelUnavailable) k.handleSend() }}
              onStop={k.handleStop}
              isStreaming={k.isStreaming}
              disabled={k.isStreaming || modelUnavailable}
              chatTitle={k.activeChat?.title}
              modelName={k.activeModel.name}
              modelColor={k.activeModel.color}
              tokenCount={k.tokenCount}
              maxTokens={200000}
              textareaRef={k.textareaRef}
              compact={k.isMobile}
              attachments={k.attachments}
              onAddFiles={k.handleAddFiles}
              onRemoveAttachment={k.handleRemoveAttachment}
              models={k.availableModels}
              overrideModel={k.overrideModel}
              onOverrideModel={k.setOverrideModel}
            />
          )}
        </main>
      </KittyRuntimeProvider>

      {k.activeView !== 'home' && <CatCorner state={k.catState} />}
      <div aria-live="polite" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
        {k.catState === 'working' ? 'Kitty is working' : k.catState === 'broke' ? 'Kitty needs attention' : k.catState === 'done' ? 'Kitty completed the task' : ''}
      </div>
      <PaperGrain />

      <ActivityCenter
        open={activityOpen}
        projection={activity.data}
        isLoading={activity.isLoading}
        error={activity.error}
        onClose={() => setActivityOpen(false)}
        onNavigate={(item) => {
          if (item.source === 'agent') {
            const sessionId = Number(item.source_id)
            setSelectedAgentSessionId(Number.isInteger(sessionId) && sessionId > 0 ? sessionId : null)
          }
          if (item.source === 'automation') {
            setSelectedAutomationRunId(item.source_id)
          }
          k.setActiveView(item.destination)
          setActivityOpen(false)
        }}
      />

      <CommandPalette
        chats={k.chats}
        onNewChat={() => { k.handleNewChat(); k.setActiveView('chat') }}
        onSelectChat={k.handleSelectChat}
        onViewChange={k.setActiveView}
        onToggleSidebar={k.handleToggleSidebar}
        onLaunchCapability={(capability) => {
          if (capability.launch === 'view' && capability.view) {
            k.setActiveView(capability.view)
            return
          }
          if (capability.launch === 'skill' && capability.skill_name) {
            k.setActiveView('chat')
            k.setInput(composeSkillLaunchInput(k.input, capability.skill_name))
            window.setTimeout(() => k.textareaRef.current?.focus(), 0)
          }
        }}
        open={cmdPaletteOpen}
        onOpenChange={setCmdPaletteOpen}
      />
    </div>
  )
}
