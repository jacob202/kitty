'use client'
import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { Chat } from '@/lib/types'
import { commandZones, contextFound, continueItems, realityCheck, signals, type DashboardTone } from '@/lib/dashboardMock'
import type { GatewayBrief } from '@/lib/gateway'
import { TaskPanel } from './TaskPanel'

interface Props {
  chats: Chat[]
  onSelectChat: (id: string) => void
  onPrompt: (text: string) => void
  brief?: GatewayBrief | null
}

export function BriefPanel({ chats, onSelectChat, onPrompt, brief }: Props) {
  const [tone, setTone] = useState<DashboardTone>('gentle')
  const recentChats = useMemo(() => {
    return [...chats]
      .filter(c => c.messages.length > 0)
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
      .slice(0, 3)
  }, [chats])

  const lastChat = recentChats[0]
  const lastLine = (lastChat?.messages.filter(m => m.role === 'assistant').at(-1)?.content || lastChat?.messages.at(-1)?.content || '')
    .replace(/```[\s\S]*?```/g, '[code]')
    .slice(0, 180)

  return (
    <div style={panelStyle}>
      <section style={heroStyle}>
        <div style={identityStyle}>
          <div className="pixel-kitty" style={{ width: 54, height: 54, borderRadius: 12 }} aria-label="Kitty" />
          <div>
            <h1 style={titleStyle}>morning, jacob :3</h1>
            <p style={subtitleStyle}>{new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</p>
          </div>
        </div>

        <div style={statusStripStyle}>
          <span>gateway: 5001</span>
          <span>{brief ? 'brief live' : 'awaiting brief'}</span>
          <span>{brief?.date ?? 'backend next'}</span>
        </div>
      </section>

      <section style={liveBriefStyle}>
        <SectionHeader title="Live brief" meta={brief?.generated_at ? 'gateway' : 'fallback'} />
        {brief?.error ? (
          <p style={bodyStyle}>{brief.error}</p>
        ) : brief ? (
          <div style={liveBriefGridStyle}>
            <div>
              <div style={liveBriefLabelStyle}>Headline</div>
              <p style={liveBriefHeadlineStyle}>{brief.headlines[0]?.title ?? 'No headline yet.'}</p>
            </div>
            <div>
              <div style={liveBriefLabelStyle}>Intention</div>
              <p style={bodyStyle}>{brief.intention || 'Waiting on the gateway brief.'}</p>
            </div>
            <div>
              <div style={liveBriefLabelStyle}>Memory</div>
              <p style={bodyStyle}>{brief.memory_snippet || 'No memory snippet returned yet.'}</p>
            </div>
          </div>
        ) : (
          <p style={bodyStyle}>The live gateway brief will appear here once the backend responds.</p>
        )}
      </section>

      <section style={topCardsStyle}>
        <StatusCard tone="blue" label="Next up" title="clean home surface" meta="now">
          Consolidate the dashboard around one useful continuation, not a wall of widgets.
        </StatusCard>
        <StatusCard tone="orange" label="Suggested fix" title="proxy default" meta="ready">
          KittyChat should default to the live gateway at 127.0.0.1:8000.
        </StatusCard>
        <StatusCard tone="green" label="Signal" title="typescript clean" meta="verified">
          Keep the UI pass buildable before plumbing deeper backend contracts.
        </StatusCard>
      </section>

      <section style={contentGridStyle}>
        <div style={activityStyle}>
          <SectionHeader title="Activity feed" meta="current lane" />
          <div style={feedStyle}>
            {recentChats.length === 0 ? (
              <p style={bodyStyle}>No recent activity. Start a chat below.</p>
            ) : recentChats.map((chat, i) => {
              const lastMsg = chat.messages.filter(m => m.role === 'assistant').at(-1)
                ?? chat.messages.at(-1)
              const preview = (lastMsg?.content ?? '')
                .replace(/```[\s\S]*?```/g, '[code]')
                .slice(0, 160)
              return (
                <FeedRow
                  key={chat.id}
                  speaker={chat.title}
                  text={preview || 'No messages yet.'}
                  highlighted={i === 0}
                />
              )
            })}
          </div>

          <div style={lastSessionBoxStyle}>
            <SectionHeader title="Continue" meta={lastChat ? 'last chat' : 'empty'} compact />
            {lastChat ? (
              <button onClick={() => onSelectChat(lastChat.id)} style={continueButtonStyle}>
                <span style={continueTitleStyle}>{lastChat.title}</span>
                <span style={continueTextStyle}>{lastLine || 'Ready to reopen this thread.'}</span>
                <span style={continueLinkStyle}>open thread -&gt;</span>
              </button>
            ) : (
              <p style={bodyStyle}>No prior chat yet. Start from a command below or type directly.</p>
            )}
          </div>
        </div>

        <aside style={sideStackStyle}>
          <div style={panelCardStyle}>
            <SectionHeader title="Reality check" meta="tone" compact />
            <div style={toggleStyle}>
              {realityCheck.tones.map(option => (
                <button
                  key={option.id}
                  onClick={() => setTone(option.id)}
                  style={{
                    ...toggleButtonStyle,
                    background: tone === option.id ? 'rgba(232, 120, 69, 0.22)' : 'transparent',
                    color: tone === option.id ? 'var(--orange-2)' : 'var(--text-muted)',
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p style={{ ...bodyStyle, marginTop: 12 }}>{realityCheck[tone]}</p>
          </div>

          <div style={panelCardStyle}>
            <SectionHeader title="Commands" meta="4" compact />
            <div style={commandsStyle}>
              {commandZones.map(zone => (
                <button key={zone.label} onClick={() => onPrompt(zone.prompt)} style={commandStyle}>
                  <span>{zone.label}</span>
                  <b style={{ color: zone.accent }}>+</b>
                </button>
              ))}
            </div>
          </div>

          <div style={panelCardStyle}>
            <SectionHeader title="Context found" meta="live" compact />
            <div style={miniListStyle}>
              {[...contextFound.slice(0, 2), signals[1], continueItems[2]].map(item => (
                <div key={`${item.label}-${item.value}`} style={{ ...miniRowStyle, borderLeftColor: item.accent }}>
                  <span style={miniLabelStyle}>{item.label}</span>
                  <span style={miniValueStyle}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={panelCardStyle}>
            <SectionHeader title="Background tasks" meta="queue" compact />
            <div style={{ marginTop: 10 }}>
              <TaskPanel />
            </div>
          </div>
        </aside>
      </section>
    </div>
  )
}

function StatusCard({ label, title, meta, tone, children }: {
  label: string
  title: string
  meta: string
  tone: 'blue' | 'orange' | 'green'
  children: string
}) {
  const accent = tone === 'blue' ? 'var(--indigo)' : tone === 'green' ? 'var(--teal)' : 'var(--orange)'
  return (
    <div style={{ ...statusCardStyle, borderTopColor: accent }}>
      <div style={cardMetaStyle}>
        <span>{label}</span>
        <span style={{ color: accent }}>{meta}</span>
      </div>
      <h2 style={cardTitleStyle}>{title}</h2>
      <p style={bodyStyle}>{children}</p>
    </div>
  )
}

function SectionHeader({ title, meta, compact = false }: { title: string; meta?: string; compact?: boolean }) {
  return (
    <div style={sectionHeaderStyle}>
      <h2 style={{ ...sectionTitleStyle, fontSize: compact ? 17 : 20 }}>{title}</h2>
      {meta && <span style={metaStyle}>{meta}</span>}
    </div>
  )
}

function FeedRow({ speaker, text, highlighted = false }: { speaker: string; text: string; highlighted?: boolean }) {
  return (
    <div style={{ ...feedRowStyle, borderLeftColor: highlighted ? 'var(--orange)' : 'var(--border)' }}>
      <span style={feedSpeakerStyle}>{speaker}</span>
      <p style={feedTextStyle}>{text}</p>
    </div>
  )
}

const panelStyle: CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: '32px 60px 160px',
  display: 'flex',
  flexDirection: 'column',
  gap: 18,
}

const heroStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 18,
  borderBottom: '1px solid var(--border-dim)',
  paddingBottom: 20,
}

const identityStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 16,
  minWidth: 0,
}

const titleStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-ui)',
  fontSize: 34,
  lineHeight: 1,
  color: 'var(--text)',
  letterSpacing: 0,
}

const subtitleStyle: CSSProperties = {
  margin: '4px 0 0',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-muted)',
}

const statusStripStyle: CSSProperties = {
  display: 'flex',
  gap: 8,
  flexWrap: 'wrap',
  justifyContent: 'flex-end',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
}

const topCardsStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 12,
}

const liveBriefStyle: CSSProperties = {
  background: 'linear-gradient(180deg, rgba(102, 119, 204, 0.08), rgba(255,255,255,0.012)), var(--panel-2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: 16,
}

const liveBriefGridStyle: CSSProperties = {
  display: 'grid',
  gap: 12,
  marginTop: 12,
}

const liveBriefLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
  marginBottom: 5,
}

const liveBriefHeadlineStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-ui)',
  fontSize: 26,
  lineHeight: 1.05,
  color: 'var(--orange-2)',
}

const statusCardStyle: CSSProperties = {
  minHeight: 126,
  background: 'linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012)), var(--panel-2)',
  border: '1px solid var(--border)',
  borderTop: '3px solid var(--indigo)',
  borderRadius: 8,
  padding: 16,
}

const cardMetaStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: 10,
  marginBottom: 10,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
}

const cardTitleStyle: CSSProperties = {
  margin: '0 0 8px',
  fontFamily: 'var(--font-ui)',
  fontSize: 28,
  lineHeight: 1,
  color: 'var(--text)',
  letterSpacing: 0,
}

const contentGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) 292px',
  gap: 14,
  alignItems: 'start',
}

const activityStyle: CSSProperties = {
  background: 'rgba(16,20,29,0.52)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 18,
  minWidth: 0,
}

const feedStyle: CSSProperties = {
  display: 'grid',
  gap: 10,
  marginTop: 14,
}

const feedRowStyle: CSSProperties = {
  borderLeft: '3px solid var(--border)',
  padding: '2px 0 2px 14px',
}

const feedSpeakerStyle: CSSProperties = {
  display: 'block',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--orange-2)',
  marginBottom: 5,
}

const feedTextStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 14,
  lineHeight: 1.7,
  color: 'var(--text-dim)',
}

const lastSessionBoxStyle: CSSProperties = {
  marginTop: 18,
  border: '1px solid var(--border-dim)',
  borderRadius: 8,
  padding: 14,
  background: 'var(--recessed)',
}

const continueButtonStyle: CSSProperties = {
  width: '100%',
  textAlign: 'left',
  display: 'grid',
  gap: 6,
  marginTop: 10,
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
}

const continueTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 24,
  color: 'var(--text)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const continueTextStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  lineHeight: 1.5,
  color: 'var(--text-muted)',
}

const continueLinkStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--teal)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
}

const sideStackStyle: CSSProperties = {
  display: 'grid',
  gap: 12,
}

const panelCardStyle: CSSProperties = {
  background: 'linear-gradient(180deg, rgba(255,255,255,0.032), rgba(255,255,255,0.012)), var(--panel)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 14,
}

const commandsStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 8,
  marginTop: 12,
}

const commandStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  minHeight: 38,
  padding: '9px 10px',
  border: '1px solid var(--border-dim)',
  borderRadius: 6,
  background: 'var(--recessed)',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-dim)',
  cursor: 'pointer',
}

const miniListStyle: CSSProperties = {
  display: 'grid',
  gap: 8,
  marginTop: 12,
}

const miniRowStyle: CSSProperties = {
  display: 'grid',
  gap: 3,
  borderLeft: '3px solid var(--indigo)',
  paddingLeft: 10,
}

const miniLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
}

const miniValueStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-dim)',
}

const toggleStyle: CSSProperties = {
  display: 'flex',
  gap: 4,
  marginTop: 12,
  padding: 3,
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 7,
}

const toggleButtonStyle: CSSProperties = {
  flex: 1,
  borderRadius: 5,
  padding: '6px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
}

const sectionHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 10,
}

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-ui)',
  lineHeight: 1,
  color: 'var(--text)',
  letterSpacing: 0,
}

const metaStyle: CSSProperties = {
  flexShrink: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
}

const bodyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  lineHeight: 1.55,
  color: 'var(--text-dim)',
}
