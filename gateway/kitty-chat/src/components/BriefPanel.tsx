'use client'
import { useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Chat } from '@/lib/types'
import { commandZones } from '@/lib/dashboardMock'
import type { GatewayBrief } from '@/lib/gateway'

interface Props {
  chats: Chat[]
  onSelectChat: (id: string) => void
  onPrompt: (text: string) => void
  brief?: GatewayBrief | null
}

const CHAT_COLOR_MAP: Record<string, string> = {
  teal:   'var(--teal)',
  indigo: 'var(--indigo)',
  orange: 'var(--orange)',
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
        badgeColor: 'var(--teal)',
        title: brief.headlines[0] ?? 'No headline',
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
        badgeColor: brief.notification_sent ? 'var(--teal)' : 'var(--orange)',
        title: brief.date ?? 'today',
        body: brief.notification_sent ? 'Brief notification sent.' : 'Brief is live and connected.',
      },
    ]
  }
  return [
    {
      label: 'NEXT UP',
      badge: 'NOW',
      badgeColor: 'var(--orange)',
      title: 'clean home surface',
      body: 'Consolidate the dashboard around one useful continuation, not a wall of widgets.',
    },
    {
      label: 'SUGGESTED FIX',
      badge: 'READY',
      badgeColor: 'var(--teal)',
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

export function BriefPanel({ chats, onSelectChat, onPrompt, brief }: Props) {
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
          <div style={greetingTitleStyle}>good morning, jacob.</div>
          <div style={greetingDateStyle}>{dateStr}</div>
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.08em',
          color: live ? 'var(--teal)' : 'var(--warning)',
        }}>
          GATEWAY: {live ? 'LIVE' : 'OFFLINE'}
        </div>
      </section>

      {/* SECTION B — Three priority cards */}
      <section style={cardsGridStyle}>
        {cards.map((card) => (
          <PriorityCardItem key={card.label} card={card} />
        ))}
      </section>

      {/* SECTION C — Activity feed */}
      {recentChats.length > 0 && (
        <section>
          <div style={sectionLabelStyle}>RECENT SESSIONS</div>
          <div>
            {recentChats.map(chat => {
              const accentColor = CHAT_COLOR_MAP[chat.color] ?? 'var(--orange)'
              return (
                <div
                  key={chat.id}
                  onClick={() => onSelectChat(chat.id)}
                  style={{
                    borderLeft: `2px solid ${accentColor}`,
                    fontFamily: 'var(--font-ui)',
                    fontSize: 13,
                    padding: '8px 24px 8px 20px',
                    borderBottom: '1px solid var(--outline-dim)',
                    cursor: 'pointer',
                    transition: 'background 0.1s',
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
        <section style={{ padding: '0 24px 20px' }}>
          <div style={sectionLabelStyle}>QUICK COMMANDS</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
            {commandZones.map(zone => (
              <button
                key={zone.label}
                onClick={() => onPrompt(zone.prompt)}
                style={commandButtonStyle}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.borderColor = 'var(--primary)'
                  el.style.color = 'var(--primary-bright)'
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLButtonElement
                  el.style.borderColor = 'var(--outline-dim)'
                  el.style.color = 'var(--text-dim)'
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
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--outline)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--outline-dim)' }}
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
  padding: '20px 24px',
  borderBottom: '1px solid var(--outline-dim)',
}

const greetingTitleStyle: CSSProperties = {
  fontFamily: 'Hanken Grotesk, system-ui, sans-serif',
  fontSize: 26,
  fontWeight: 600,
  color: 'var(--text)',
  lineHeight: 1.15,
}

const greetingDateStyle: CSSProperties = {
  fontFamily: 'JetBrains Mono, ui-monospace, monospace',
  fontSize: 11,
  color: 'var(--text-muted)',
  marginTop: 4,
}

const cardsGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 12,
  padding: '16px 24px',
}

const cardBaseStyle: CSSProperties = {
  background: 'var(--surface-low)',
  border: '1px solid var(--outline-dim)',
  borderRadius: 6,
  padding: '14px 16px',
  transition: 'border-color 0.15s',
  cursor: 'default',
}

const cardLabelStyle: CSSProperties = {
  fontFamily: 'JetBrains Mono, ui-monospace, monospace',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  color: 'var(--text-muted)',
}

const cardBadgeStyle: CSSProperties = {
  fontFamily: 'JetBrains Mono, ui-monospace, monospace',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  border: '1px solid',
  borderRadius: 2,
  padding: '1px 6px',
  background: 'transparent',
}

const cardTitleStyle: CSSProperties = {
  fontFamily: 'Hanken Grotesk, system-ui, sans-serif',
  fontSize: 15,
  fontWeight: 600,
  marginTop: 8,
  color: 'var(--text)',
}

const cardBodyStyle: CSSProperties = {
  fontFamily: 'Hanken Grotesk, system-ui, sans-serif',
  fontSize: 13,
  color: 'var(--text-dim)',
  lineHeight: 1.55,
  marginTop: 6,
}

const sectionLabelStyle: CSSProperties = {
  fontFamily: 'JetBrains Mono, ui-monospace, monospace',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  color: 'var(--text-muted)',
  padding: '16px 24px 8px',
}

const commandButtonStyle: CSSProperties = {
  border: '1px solid var(--outline-dim)',
  borderRadius: 4,
  padding: '6px 14px',
  fontFamily: 'JetBrains Mono, ui-monospace, monospace',
  fontSize: 12,
  background: 'transparent',
  color: 'var(--text-dim)',
  cursor: 'pointer',
  transition: 'border-color 0.15s, color 0.15s',
}
