'use client'
import { useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Chat } from '@/lib/types'
import { commandZones } from '@/lib/dashboardMock'
import type { GatewayBrief, GatewayHeadline, GatewayTodo } from '@/lib/gateway'
import { BriefStrip } from '@/components/BriefStrip'
import { TodayCompass, type PriorityItem } from '@/components/TodayCompass'

function headlineText(h: string | GatewayHeadline): string {
  return typeof h === 'string' ? h : h.title
}

const USER_DISPLAY_NAME = 'jacob'

function greetingTime(): string {
  const h = new Date().getHours()
  if (h < 5) return 'still up'
  if (h < 12) return 'good morning'
  if (h < 17) return 'good afternoon'
  if (h < 21) return 'good evening'
  return 'late night'
}

interface Props {
  chats: Chat[]
  onSelectChat: (id: string) => void
  onPrompt: (text: string) => void
  brief?: GatewayBrief | null
  todos?: GatewayTodo[]
  loading?: boolean
}

const CHAT_COLOR_MAP: Record<string, string> = {
  teal:   'var(--teal)',
  indigo: 'var(--indigo)',
  orange: 'var(--primary)',
  purple: 'var(--purple)',
  mint:   'var(--mint)',
  blue:   'var(--blue)',
  yellow: 'var(--yellow)',
  pink:   'var(--pink-blue)',
}

function gatewayIsLive(brief: GatewayBrief | null | undefined): boolean {
  if (!brief) return false
  if (brief.error) return false
  return true
}

function activeTodos(todos: GatewayTodo[]): GatewayTodo[] {
  return todos.filter(t => t.status === 'pending' || t.status === 'in_progress')
}

function weatherFromHeadlines(headlines: GatewayBrief['headlines']): string | null {
  if (!headlines?.length) return null
  const match = headlines.find(h => {
    const text = headlineText(h).toLowerCase()
    return text.includes('weather') || text.includes('forecast') || text.includes('°')
  })
  return match ? headlineText(match) : null
}

function buildCompassItems(
  brief: GatewayBrief | null | undefined,
  todos: GatewayTodo[],
  onPrompt: (text: string) => void,
): PriorityItem[] {
  const items: PriorityItem[] = []
  const active = activeTodos(todos)

  if (brief?.intention?.trim()) {
    items.push({
      id: 'intention',
      title: brief.intention.trim(),
      description: brief.memory_snippet?.slice(0, 120) || undefined,
      priority: 'high',
      icon: '🎯',
      onSelect: () => onPrompt(brief.intention!.trim()),
    })
  }

  brief?.headlines?.slice(0, 4).forEach((headline, index) => {
    const title = headlineText(headline)
    if (!title) return
    items.push({
      id: `headline-${index}`,
      title,
      description: typeof headline === 'object' ? headline.snippet?.slice(0, 120) : undefined,
      priority: index === 0 ? 'medium' : 'low',
      icon: '📰',
    })
  })

  active.slice(0, 3).forEach(todo => {
    items.push({
      id: `todo-${todo.id}`,
      title: todo.content,
      description: todo.active_form || undefined,
      priority: todo.status === 'in_progress' ? 'high' : 'medium',
      icon: '☐',
      onSelect: () => onPrompt(todo.content),
    })
  })

  return items
}

export function BriefPanel({
  chats,
  onSelectChat,
  onPrompt,
  brief,
  todos = [],
  loading = false,
}: Props) {
  const recentChats = useMemo(() => {
    return [...chats]
      .filter(c => c.messages.length > 0)
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
      .slice(0, 6)
  }, [chats])

  const live = gatewayIsLive(brief)
  const dateStr = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
  const openTodos = activeTodos(todos)
  const focusTodo = openTodos.find(t => t.status === 'in_progress') ?? openTodos[0]
  const compassItems = useMemo(
    () => buildCompassItems(brief, todos, onPrompt),
    [brief, todos, onPrompt],
  )

  return (
    <div style={panelStyle}>
      <section style={greetingBarStyle}>
        <div>
          <div style={greetingTitleStyle}>{greetingTime()}, {USER_DISPLAY_NAME}.</div>
          <div style={greetingDateStyle}>{dateStr}</div>
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.08em',
          color: live ? 'var(--mint)' : 'var(--error)',
        }}>
          GATEWAY: {live ? 'LIVE' : 'OFFLINE'}
        </div>
      </section>

      {loading ? (
        <section role="status" aria-label="loading brief" style={sectionPadStyle}>
          <div style={{ ...stripSkeletonStyle, height: 72, opacity: 0.35 }} />
          <div style={{ ...stripSkeletonStyle, height: 140, opacity: 0.25, marginTop: 16 }} />
        </section>
      ) : (
        <section style={sectionPadStyle}>
          <BriefStrip
            intention={brief?.intention ?? null}
            weather={weatherFromHeadlines(brief?.headlines)}
            overdueCount={openTodos.length}
            focusText={focusTodo?.content ?? null}
          />
          <div style={{ marginTop: 16 }}>
            <TodayCompass
              items={compassItems}
              onItemSelect={item => {
                if (!item.onSelect) onPrompt(item.title)
              }}
            />
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
                  onClick={() => onSelectChat(chat.id)}
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

      {commandZones.length > 0 && (
        <section style={{ padding: '24px 24px 40px' }}>
          <div style={{...sectionLabelStyle, padding: '0 0 12px'}}>QUICK COMMANDS</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' as const }}>
            {commandZones.map(zone => (
              <button
                key={zone.label}
                onClick={() => onPrompt(zone.prompt)}
                style={commandButtonStyle}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.borderColor = 'var(--primary)'
                  el.style.color = 'var(--primary-bright)'
                  el.style.background = 'var(--surface-low)'
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.borderColor = 'var(--border)'
                  el.style.color = 'var(--text-dim)'
                  el.style.background = 'transparent'
                }}
              >
                {zone.label}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

const panelStyle: CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: 0,
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

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
  color: 'var(--text-muted)',
  padding: '24px 32px 12px',
}

const commandButtonStyle: CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '8px 16px',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  background: 'transparent',
  color: 'var(--text-dim)',
  cursor: 'pointer',
  transition: 'all 0.2s ease',
}
