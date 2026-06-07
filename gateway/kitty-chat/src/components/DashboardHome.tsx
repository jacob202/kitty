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

          {brief?.summary_bullets && brief.summary_bullets.length > 0 && (
            <div style={summaryCardStyle}>
              <div style={summaryLabelStyle}>WHAT&apos;S INTERESTING TODAY</div>
              <ul style={summaryListStyle}>
                {brief.summary_bullets.map((line, i) => (
                  <li key={i} style={summaryLineStyle}>{line}</li>
                ))}
              </ul>
            </div>
          )}

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
}

const stripSkeletonStyle: CSSProperties = {
  background: 'var(--surface-mid)',
  borderRadius: 10,
  border: '1px solid var(--border)',
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
  gap: 12,
  marginTop: 12,
  alignContent: 'start',
}

const summaryCardStyle: CSSProperties = {
  marginTop: 12,
  padding: '12px 14px',
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
}

const summaryLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.12em',
  color: 'var(--text-muted)',
  marginBottom: 8,
}

const summaryListStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 18,
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

const summaryLineStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  lineHeight: 1.5,
  color: 'var(--text)',
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
