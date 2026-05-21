'use client'
import { Chat } from '@/lib/types'
import type { GatewayBrief, GatewaySearchSnapshot } from '@/lib/gateway'

interface Props {
  chats: Chat[]
  activeChat: Chat | null
  isStreaming: boolean
  brief?: GatewayBrief | null
  search?: GatewaySearchSnapshot | null
  /** Set when /search failed for the current thread (so we distinguish offline from empty hits). */
  searchGatewayError?: string | null
  activeModelName?: string
}

export function RightBar({
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
  const dateStr = new Date().toLocaleDateString([], { month: 'short', day: 'numeric' })
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <aside style={{
      width: 'var(--rightbar)',
      borderLeft: '1px solid var(--border)',
      padding: '18px 14px',
      overflowY: 'auto',
      background: 'rgba(16, 20, 29, 0.74)',
      backdropFilter: 'blur(10px)',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
          color: 'var(--text-muted)', letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>today</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{dateStr}</span>
      </div>

      <RightCard accent="var(--pink-blue)" title="Sessions" value={`${chats.length}`}>
        <p style={bodyStyle}>{msgCount} total messages</p>
      </RightCard>

      {activeModelName && (
        <RightCard accent="var(--yellow)" title="Model">
          <p style={bodyStyle}>{activeModelName}</p>
        </RightCard>
      )}

      <RightCard accent="var(--orange)" title="Kitty">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 13,
            display: 'grid', placeItems: 'center',
            background: 'var(--recessed)',
            border: '1px solid var(--border)',
            fontFamily: 'var(--font-ui)', fontSize: 16,
            color: isStreaming ? 'var(--purple)' : 'var(--orange)',
            animation: isStreaming ? 'none' : undefined,
          }}>
            {isStreaming ? '=^._.^=' : '=^•ﻌ•^='}
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
              {isStreaming ? 'thinking…' : 'online'}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              {isStreaming ? 'generating response' : 'ready for anything'}
            </div>
          </div>
        </div>
      </RightCard>

      {brief && (
        <RightCard accent="var(--mint)" title="Brief">
          <p style={bodyStyle}>{brief.intention || brief.headlines[0] || 'Live brief connected.'}</p>
        </RightCard>
      )}

      {lastAi && (
        <RightCard accent="var(--indigo)" title="Last reply">
          <p style={bodyStyle}>
            {lastAi.content.replace(/```[\s\S]*?```/g, '[code]').slice(0, 120)}
            {lastAi.content.length > 120 ? '…' : ''}
          </p>
        </RightCard>
      )}

      {activeChat && activeChat.messages.length > 0 && (
        <RightCard accent="var(--teal)" title="Context" value={`${activeChat.messages.length} msg`}>
          <p style={bodyStyle}>{activeChat.title}</p>
        </RightCard>
      )}

      {searchGatewayError && !search && (
        <RightCard accent="var(--warning)" title="Search unavailable">
          <p style={bodyStyle}>{searchGatewayError}</p>
        </RightCard>
      )}

      {search && (
        <RightCard accent="var(--pink-blue)" title="Gateway search" value={search.query || 'live'}>
          {search.counts.memories + search.counts.knowledge + search.counts.journal + search.counts.todos > 0 ? (
            <div style={{ display: 'grid', gap: 8, marginTop: 6 }}>
              {([
                ['Memories', search.sections.memories[0]],
                ['Knowledge', search.sections.knowledge[0]],
                ['Journal', search.sections.journal[0]],
                ['Todos', search.sections.todos[0]],
              ] as const)
                .filter(([, value]) => Boolean(value))
                .map(([label, value]) => (
                  <div key={label}>
                    <div style={labelStyle}>{label}</div>
                    <p style={bodyStyle}>{value}</p>
                  </div>
                ))}
            </div>
          ) : (
            <p style={bodyStyle}>No grouped search hits yet for this thread.</p>
          )}
        </RightCard>
      )}

      <RightCard accent="var(--mint)" title="Time">
        <p style={bodyStyle}>{timeStr} · {new Date().toLocaleDateString([], { weekday: 'long' })}</p>
      </RightCard>
    </aside>
  )
}

const bodyStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-dim)',
  lineHeight: 1.5,
  marginTop: 4,
}

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
}

function RightCard({ children, accent, title, value }: {
  children?: React.ReactNode
  accent: string
  title: string
  value?: string
}) {
  return (
    <div style={{
      background: `linear-gradient(180deg, rgba(255,255,255,0.024), transparent), var(--panel)`,
      border: '1px solid var(--border)',
      borderLeft: `3px solid ${accent}`,
      borderRadius: 'var(--radius-sm)',
      padding: '14px',
      marginBottom: 12,
    }}>
      <h3 style={{
        margin: '0 0 4px',
        fontSize: 13,
        letterSpacing: '-0.02em',
        fontFamily: 'var(--font-mono)',
        fontWeight: 700,
        color: 'var(--text)',
        display: 'flex',
        justifyContent: 'space-between',
        gap: 8,
      }}>
        {title}
        {value && <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--yellow)', fontWeight: 900, fontSize: 12 }}>{value}</span>}
      </h3>
      {children}
    </div>
  )
}
