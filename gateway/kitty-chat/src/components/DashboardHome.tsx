'use client'
import type { CSSProperties } from 'react'
import { BriefStrip } from '@/components/BriefStrip'
import { TodayCompass, type PriorityItem } from '@/components/TodayCompass'
import { LoopWatch } from '@/components/LoopWatch'
import { PromptToolkit } from '@/components/PromptToolkit'
import { InsightFeed } from '@/components/InsightFeed'
import type { GatewayBrief, GatewayTodo, GatewayLoop, GatewayInsight } from '@/lib/gateway'

interface Props {
  brief: GatewayBrief | null
  todos: GatewayTodo[]
  loops: GatewayLoop[]
  insights: GatewayInsight[]
  promptTemplates: Array<{ id: string | number; title: string; content: string; category?: string; icon?: string }>
  onPromptSelect?: (content: string) => void
  onLoopToggle?: (loopId: string) => void
  onInsightDismiss?: (insightId: string) => void
  onInsightAction?: (insightId: string, actionId: string) => void
}

export function DashboardHome({
  brief,
  todos,
  loops,
  insights,
  promptTemplates,
  onPromptSelect,
  onLoopToggle,
  onInsightDismiss,
  onInsightAction,
}: Props) {
  const intention = brief?.intention ?? null
  const weather = brief?.headlines.find(h => typeof h === 'string' && h.toLowerCase().includes('weather'))
    ? (brief.headlines[0] as string)
    : null

  const overdueCount = todos.filter(t => t.status !== 'completed').length
  const focusTodo = todos.find(t => t.status !== 'completed' && t.active_form?.toLowerCase().includes('focus'))

  const priorityItems: PriorityItem[] = todos
    .filter(t => t.status !== 'completed')
    .map(t => ({
      id: t.id,
      title: t.content,
      priority: t.sort_order && t.sort_order < 3 ? 'high' : t.sort_order && t.sort_order < 6 ? 'medium' : 'low',
      onSelect: () => onPromptSelect?.(t.content),
    }))

  return (
    <div style={containerStyle}>
      <div style={topSectionStyle}>
        <BriefStrip
          intention={intention}
          weather={weather}
          overdueCount={overdueCount}
          focusText={focusTodo?.content || null}
        />
      </div>

      <div style={gridStyle}>
        <section style={sectionStyle}>
          <TodayCompass
            items={priorityItems}
            title="Today's Compass"
            onItemSelect={item => onPromptSelect?.(item.title)}
          />
        </section>

        <section style={sectionStyle}>
          <LoopWatch loops={loops} onToggle={onLoopToggle} title="Loop Watch" />
        </section>

        <section style={sectionStyle}>
          <PromptToolkit
            templates={promptTemplates}
            onSelect={tpl => onPromptSelect?.(tpl.content)}
            title="Prompt Toolkit"
          />
        </section>

        <section style={sectionStyle}>
          <InsightFeed
            insights={insights}
            onDismiss={onInsightDismiss}
            onAction={onInsightAction}
            title="Insights"
          />
        </section>
      </div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 16,
  padding: '20px 24px',
  height: '100%',
  overflowY: 'auto',
}

const topSectionStyle: CSSProperties = {
  flexShrink: 0,
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gap: 16,
  alignContent: 'start',
}

const sectionStyle: CSSProperties = {
  minWidth: 0,
}
