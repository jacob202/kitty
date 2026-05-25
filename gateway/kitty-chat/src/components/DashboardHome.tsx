'use client'
import { useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Chat } from '@/lib/types'
import { BriefStrip } from '@/components/BriefStrip'
import { TodayCompass } from '@/components/TodayCompass'
import { LoopWatch } from '@/components/LoopWatch'
import { PromptToolkit } from '@/components/PromptToolkit'
import { InsightFeed } from '@/components/InsightFeed'
import type {
  GatewayBrief,
  GatewayTodo,
  GatewayLoop,
  GatewayInsight,
  GatewayWeather,
} from '@/lib/gateway'
import {
  USER_DISPLAY_NAME,
  greetingTime,
  activeTodos,
  focusTodo,
  buildCompassItems,
  gatewayBriefIsLive,
  recentChatsWithMessages,
  resolveWeatherText,
} from '@/lib/dashboardHome'

interface Props {
  brief: GatewayBrief | null
  todos: GatewayTodo[]
  loops: GatewayLoop[]
  insights: GatewayInsight[]
  weather?: GatewayWeather | null
  promptTemplates: Array<{ id: string | number; title: string; content: string; category?: string }>
  chats?: Chat[]
  loading?: boolean
  onSelectChat?: (id: string) => void
  onPromptSelect?: (content: string) => void
  onLoopToggle?: (loopId: string) => void
  onInsightDismiss?: (insightId: string) => void
  onInsightAction?: (insightId: string, actionId: string) => void
}

const CHAT_COLOR_MAP: Record<string, string> = {
  teal: 'var(--teal)',
  indigo: 'var(--indigo)',
  orange: 'var(--primary)',
  purple: 'var(--purple)',
  mint: 'var(--mint)',
  blue: 'var(--blue)',
  yellow: 'var(--yellow)',
  pink: 'var(--pink-blue)',
}

export function DashboardHome({
  brief,
  todos,
  loops,
  insights,
  weather = null,
  promptTemplates,
  chats = [],
  loading = false,
  onSelectChat,
  onPromptSelect,
  onLoopToggle,
  onInsightDismiss,
  onInsightAction,
}: Props) {
  const live = gatewayBriefIsLive(brief)
  const dateStr = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
  const openTodos = activeTodos(todos)
  const focus = focusTodo(todos)
  const weatherText = resolveWeatherText(weather, brief)
  const compassItems = useMemo(
    () => buildCompassItems(brief, todos, text => onPromptSelect?.(text)),
    [brief, todos, onPromptSelect],
  )
  const recentChats = useMemo(() => recentChatsWithMessages(chats), [chats])

  return (
    <div style={panelStyle}>
      <section style={greetingBarStyle}>
        <div>
          <div style={greetingTitleStyle}>{greetingTime()}, {USER_DISPLAY_NAME}.</div>
          <div style={greetingDateStyle}>{dateStr}</div>
        </div>
        {live && (
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            textTransform: 'uppercase' as const,
            letterSpacing: '0.08em',
            color: 'var(--mint)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--mint)', display: 'inline-block' }} />
            live
          </div>
        )}
      </section>

      {loading ? (
        <section role="status" aria-label="loading dashboard" style={sectionPadStyle}>
          <div style={{ ...stripSkeletonStyle, height: 72, opacity: 0.35 }} />
          <div style={{ ...stripSkeletonStyle, height: 240, opacity: 0.25, marginTop: 16 }} />
        </section>
      ) : (
        <section style={sectionPadStyle}>
          <BriefStrip
            intention={brief?.intention ?? null}
            weather={weatherText}
            overdueCount={openTodos.length}
            focusText={focus?.content ?? null}
          />

          <div style={gridStyle}>
            <section style={sectionStyle}>
              <TodayCompass
                items={compassItems}
                title="Today's Compass"
                onItemSelect={item => {
                  if (!item.onSelect) onPromptSelect?.(item.title)
                }}
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
        </section>
      )}

      {recentChats.length > 0 && (
        <section>
          <div style={sectionLabelStyle}>RECENT SESSIONS</div>
          <div>
            {recentChats.map(chat => {
              const accentColor = CHAT_COLOR_MAP[chat.color] ?? 'var(--primary)'
              return (
                <div
                  key={chat.id}
                  onClick={() => onSelectChat?.(chat.id)}
                  style={{
                    borderLeft: `2px solid ${accentColor}`,
                    fontFamily: 'var(--font-ui)',
                    fontSize: 14,
                    padding: '10px 24px 10px 20px',
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    color: 'var(--text)',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--surface-low)' }}
                  onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
                >
                  {chat.title}
                </div>
              )
            })}
          </div>
        </section>
      )}
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
  padding: '24px 32px',
  borderBottom: '1px solid var(--border)',
}

const greetingTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 28,
  fontWeight: 600,
  color: 'var(--text)',
  lineHeight: 1.15,
}

const greetingDateStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-muted)',
  marginTop: 6,
}

const sectionPadStyle: CSSProperties = {
  padding: '24px 32px',
}

const stripSkeletonStyle: CSSProperties = {
  background: 'var(--surface-mid)',
  borderRadius: 10,
  border: '1px solid var(--border)',
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gap: 16,
  marginTop: 16,
  alignContent: 'start',
}

const sectionStyle: CSSProperties = {
  minWidth: 0,
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
  color: 'var(--text-muted)',
  padding: '24px 32px 12px',
}
