'use client'
import { useMemo, useRef } from 'react'
import type { CSSProperties } from 'react'
import { TodayCompass } from '@/components/TodayCompass'
import { CapturePanel } from '@/components/CapturePanel'
import { NeedsYou } from '@/components/NeedsYou'
import { WhatChanged } from '@/components/WhatChanged'
import { OpenLoops } from '@/components/OpenLoops'
import type {
  GatewayBrief,
  GatewayTodo,
  GatewayAction,
  GatewayTriageEntry,
  GatewayStateChange,
  GatewaySignal,
} from '@/lib/gateway'
import { greetingTime, buildCompassItems } from '@/lib/dashboardHome'

interface Props {
  brief: GatewayBrief | null
  todos: GatewayTodo[]
  todosLoading?: boolean
  briefLoading?: boolean
  todayError: string | null

  proposedActions: GatewayAction[]
  proposedActionsLoading?: boolean
  proposedActionsError: string | null
  busyActionId?: number | null
  onApproveAction: (actionId: number) => void
  onRejectAction: (actionId: number) => void

  needsJacob: GatewayTriageEntry[]
  needsJacobLoading?: boolean
  needsJacobError: string | null

  stateChanges: GatewayStateChange[]
  newSignals: GatewaySignal[]
  stateChangesNote?: string
  hasBaseline: boolean
  stateChangesLoading?: boolean
  stateChangesError: string | null
  onSnapshot: () => void
  snapshotBusy?: boolean

  untriagedCount: number
  triageBusy?: boolean
  onRunTriage: () => void

  onPromptSelect: (text: string) => void
}

export function HomeState({
  brief,
  todos,
  todosLoading = false,
  briefLoading = false,
  todayError,
  proposedActions,
  proposedActionsLoading = false,
  proposedActionsError,
  busyActionId = null,
  onApproveAction,
  onRejectAction,
  needsJacob,
  needsJacobLoading = false,
  needsJacobError,
  stateChanges,
  newSignals,
  stateChangesNote,
  hasBaseline,
  stateChangesLoading = false,
  stateChangesError,
  onSnapshot,
  snapshotBusy = false,
  untriagedCount,
  triageBusy = false,
  onRunTriage,
  onPromptSelect,
}: Props) {
  const needsYouRef = useRef<HTMLDivElement>(null)
  const dateStr = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
  const compassItems = useMemo(
    () => buildCompassItems(brief, todos, (text) => onPromptSelect(text)),
    [brief, todos, onPromptSelect],
  )

  const jumpToNeedsYou = () => needsYouRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  const decideInChat = (entry: GatewayTriageEntry) => {
    onPromptSelect(`Help me decide what to do with this: ${entry.text ?? `inbox entry ${entry.inbox_id}`}`)
  }

  return (
    <div style={panelStyle}>
      <section style={greetingBarStyle}>
        <div>
          <div style={greetingTitleStyle}>{greetingTime()}.</div>
          <div style={greetingDateStyle}>{dateStr}</div>
        </div>
      </section>

      <section style={sectionPadStyle}>
        <OpenLoops
          untriagedCount={untriagedCount}
          proposedCount={proposedActions.length}
          needsJacobCount={needsJacob.length}
          triageBusy={triageBusy}
          onRunTriage={onRunTriage}
          onJumpToNeedsYou={jumpToNeedsYou}
        />

        <div ref={needsYouRef}>
          <NeedsYou
            actions={proposedActions}
            actionsLoading={proposedActionsLoading}
            actionsError={proposedActionsError}
            needsJacob={needsJacob}
            needsJacobLoading={needsJacobLoading}
            needsJacobError={needsJacobError}
            busyActionId={busyActionId}
            onApprove={onApproveAction}
            onReject={onRejectAction}
            onDecideInChat={decideInChat}
          />
        </div>

        <div style={gridStyle}>
          <WhatChanged
            changes={stateChanges}
            newSignals={newSignals}
            note={stateChangesNote}
            hasBaseline={hasBaseline}
            isLoading={stateChangesLoading}
            error={stateChangesError}
            onSnapshot={onSnapshot}
            snapshotBusy={snapshotBusy}
          />

          <TodayCompass
            items={compassItems}
            title="Today"
            isLoading={todosLoading || briefLoading}
            error={todayError}
            onItemSelect={(item) => {
              if (!item.onSelect) onPromptSelect(item.title)
            }}
          />
        </div>

        <CapturePanel />
      </section>
    </div>
  )
}

const panelStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 0,
  paddingBottom: 160,
}

const greetingBarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 20px',
  borderBottom: '1px solid var(--border)',
}

const greetingTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 22,
  fontWeight: 600,
  color: 'var(--text)',
  lineHeight: 1.15,
}

const greetingDateStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
  marginTop: 4,
}

const sectionPadStyle: CSSProperties = {
  padding: '14px 20px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
  gap: 12,
  alignContent: 'start',
}
