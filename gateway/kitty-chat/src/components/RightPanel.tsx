'use client'
import { Chat, STREAMING_LABEL } from '@/lib/types'
import type { GatewayBrief, GatewayHeadline, GatewaySearchSnapshot } from '@/lib/gateway'
import { CronPanel } from './CronPanel'
import { sectionLabel } from '@/lib/ui'

interface Props {
  chats: Chat[]
  activeChat: Chat | null
  isStreaming: boolean
  brief?: GatewayBrief | null
  search?: GatewaySearchSnapshot | null
  searchGatewayError?: string | null
  activeModelName?: string
}

export function RightPanel({
  chats,
  activeChat,
  isStreaming,
  brief,
  search,
  searchGatewayError,
  activeModelName,
}: Props) {
  const msgCount = chats.reduce((sum, c) => sum + c.messages.length, 0)
  const lastAi = activeChat?.messages.filter(m => m.role === 'assistant').at(-1)
  const dateStr = new Date().toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <aside style={{
      width: 'var(--rightbar)',
      borderLeft: '1px solid var(--border)',
      overflowY: 'auto',
      background: 'var(--surface)',
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px 8px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <span style={{ ...sectionLabel, letterSpacing: '0.16em' }}>today</span>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-muted)',
        }}>{dateStr}</span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: '8px 0', overflowY: 'auto' }}>

        {/* Quick stats strip */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 6,
          padding: '0 12px 8px',
          borderBottom: '1px solid var(--border)',
          marginBottom: 8,
        }}>
          <Stat label="Sessions" value={String(chats.length)} />
          <Stat label="Messages" value={String(msgCount)} />
        </div>

        {/* Cron schedules */}
        <CronPanel />

        {/* Time */}
        <PanelRow label="Time">
          <span style={valueStyle}>{timeStr}</span>
          <span style={subStyle}>{new Date().toLocaleDateString([], { weekday: 'long' })}</span>
        </PanelRow>

        {/* Active model */}
        {activeModelName && (
          <PanelRow label="Model">
            <span style={valueStyle}>{activeModelName}</span>
          </PanelRow>
        )}

        {/* Kitty status */}
        <PanelRow label="Kitty">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: isStreaming ? 'var(--primary)' : 'var(--mint)',
              flexShrink: 0,
              display: 'inline-block',
              boxShadow: isStreaming
                ? '0 0 8px rgba(224,122,95,0.5)'
                : '0 0 8px rgba(115,217,159,0.4)',
            }} />
            <div>
              <div style={valueStyle}>{isStreaming ? STREAMING_LABEL : 'online'}</div>
              <div style={subStyle}>{isStreaming ? 'generating…' : 'ready for anything'}</div>
            </div>
          </div>
        </PanelRow>

        {/* Brief */}
        {brief && (
          <PanelRow label="Brief">
            <span style={valueStyle}>
              {brief.intention || (typeof brief.headlines[0] === 'string' ? brief.headlines[0] : (brief.headlines[0] as GatewayHeadline | undefined)?.title) || 'Live brief connected.'}
            </span>
          </PanelRow>
        )}

        {/* Active context */}
        {activeChat && activeChat.messages.length > 0 && (
          <PanelRow label="Context">
            <span style={valueStyle}>{activeChat.title}</span>
            <span style={subStyle}>{activeChat.messages.length} messages</span>
          </PanelRow>
        )}

        {/* Last AI reply */}
        {lastAi && (
          <PanelRow label="Last reply">
            <span style={{ ...valueStyle, fontFamily: 'var(--font-ui)', fontWeight: 400, fontSize: 12, lineHeight: 1.5 }}>
              {lastAi.content.replace(/```[\s\S]*?```/g, '[code]').slice(0, 100)}
              {lastAi.content.length > 100 ? '…' : ''}
            </span>
          </PanelRow>
        )}

        {/* Search error */}
        {searchGatewayError && !search && (
          <PanelRow label="Search">
            <span style={{ ...subStyle, color: 'var(--warning)' }}>unavailable</span>
          </PanelRow>
        )}

        {/* Gateway search results */}
        {search && (
          <PanelRow label={`Search · ${search.query || 'live'}`}>
            {search.counts.memories + search.counts.knowledge + search.counts.journal + search.counts.todos > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                {([
                  ['Mem', search.sections.memories[0]],
                  ['KB', search.sections.knowledge[0]],
                  ['Journal', search.sections.journal[0]],
                  ['Todos', search.sections.todos[0]],
                ] as const)
                  .filter(([, v]) => Boolean(v))
                  .map(([label, v]) => (
                    <div key={label}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' as const }}>{label}</div>
                      <div style={valueStyle}>{v}</div>
                    </div>
                  ))}
              </div>
            ) : (
              <span style={subStyle}>no hits yet</span>
            )}
          </PanelRow>
        )}
      </div>
    </aside>
  )
}

const valueStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text)',
  display: 'block',
}

const subStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  display: 'block',
  marginTop: 2,
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      background: 'var(--surface-low)',
      border: '1px solid var(--border)',
      borderRadius: 6,
      padding: '6px 10px',
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: 'var(--text-muted)',
        letterSpacing: '0.14em',
        textTransform: 'uppercase' as const,
        marginBottom: 2,
      }}>{label}</div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 16,
        fontWeight: 700,
        color: 'var(--text)',
        lineHeight: 1,
      }}>{value}</div>
    </div>
  )
}

function PanelRow({ label, children }: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div style={{
      padding: '6px 12px 6px 10px',
      borderLeft: '2px solid var(--border-dim)',
      marginLeft: 12,
      marginBottom: 6,
    }}>
      <div style={{ ...sectionLabel, marginBottom: 2 }}>{label}</div>
      {children}
    </div>
  )
}
