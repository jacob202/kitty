'use client'
import { useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Chat } from '@/lib/types'
import { commandZones } from '@/lib/dashboardMock'
import type { GatewayBrief, GatewayHeadline } from '@/lib/gateway'

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

interface PriorityCard {
  label: string
  badge: string
  badgeColor: string
  title: string
  body: string
}

function buildCards(brief: GatewayBrief | null | undefined): PriorityCard[] {
  if (brief && !brief.error && brief.headlines?.length) {
    return [
      {
        label: 'HEADLINE',
        badge: 'LIVE',
        badgeColor: 'var(--mint)',
        title: headlineText(brief.headlines[0]) || 'No headline',
        body: brief.intention ?? '',
      },
      {
        label: 'MEMORY',
        badge: 'GATEWAY',
        badgeColor: 'var(--secondary)',
        title: 'context loaded',
        body: brief.memory_snippet ?? 'No memory snippet returned.',
      },
      {
        label: 'STATUS',
        badge: brief.notification_sent ? 'SENT' : 'LIVE',
        badgeColor: brief.notification_sent ? 'var(--mint)' : 'var(--primary)',
        title: brief.date ?? 'today',
        body: brief.notification_sent ? 'Brief notification sent.' : 'Brief is live and connected.',
      },
    ]
  }
  return [
    {
      label: 'NEXT UP',
      badge: 'NOW',
      badgeColor: 'var(--primary)',
      title: 'clean home surface',
      body: 'Consolidate the dashboard around one useful continuation, not a wall of widgets.',
    },
    {
      label: 'SUGGESTED FIX',
      badge: 'READY',
      badgeColor: 'var(--mint)',
      title: 'proxy default',
      body: 'KittyChat should default to the live gateway at 127.0.0.1:8000.',
    },
    {
      label: 'SIGNAL',
      badge: 'VERIFIED',
      badgeColor: 'var(--secondary)',
      title: 'typescript clean',
      body: 'Keep the UI pass buildable before plumbing deeper backend contracts.',
    },
  ]
}

export function BriefPanel({ chats, onSelectChat, onPrompt, brief, loading = false }: Props) {
  const recentChats = useMemo(() => {
    return [...chats]
      .filter(c => c.messages.length > 0)
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
      .slice(0, 6)
  }, [chats])

  const cards = buildCards(brief)
  const live = gatewayIsLive(brief)
  const dateStr = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })

  return (
    <div style={panelStyle}>
      {/* SECTION A — Greeting bar */}
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

      {/* SECTION B — Three priority cards (or loading skeleton) */}
      {loading ? (
        <section
          role="status"
          aria-label="loading brief"
          style={cardsGridStyle}
        >
          {[0, 1, 2].map(i => (
            <div
              key={i}
              style={{
                ...cardBaseStyle,
                height: 104,
                opacity: 0.35,
                background: 'var(--surface-mid)',
                animation: 'none',
              }}
            />
          ))}
        </section>
      ) : (
        <section style={cardsGridStyle}>
          {cards.map((card) => (
            <PriorityCardItem key={card.label} card={card} />
          ))}
        </section>
      )}

      {/* SECTION C — Activity feed */}
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

      {/* SECTION D — Quick command shortcuts */}
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

function PriorityCardItem({ card }: { card: PriorityCard }) {
  return (
    <div
      style={cardBaseStyle}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = card.badgeColor }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={cardLabelStyle}>{card.label}</span>
        <span style={{ ...cardBadgeStyle, borderColor: card.badgeColor, color: card.badgeColor }}>
          {card.badge}
        </span>
      </div>
      <div style={cardTitleStyle}>{card.title}</div>
      <div style={cardBodyStyle}>{card.body}</div>
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

const cardsGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 16,
  padding: '24px 32px',
}

const cardBaseStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '16px 20px',
  transition: 'border-color 0.2s ease',
  cursor: 'default',
}

const cardLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
  color: 'var(--text-muted)',
}

const cardBadgeStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  border: '1px solid',
  borderRadius: 4,
  padding: '2px 6px',
  background: 'transparent',
}

const cardTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 16,
  fontWeight: 600,
  marginTop: 10,
  color: 'var(--text)',
}

const cardBodyStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 14,
  color: 'var(--text-dim)',
  lineHeight: 1.5,
  marginTop: 6,
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
