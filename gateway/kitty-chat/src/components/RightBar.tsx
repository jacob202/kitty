'use client'
import { useState, useEffect } from 'react'
import { Chat } from '@/lib/types'
import type { GatewayBrief, GatewaySearchSnapshot, GatewayWeather, GatewaySkill, GatewayAgent } from '@/lib/gateway'
import { fetchGatewayWeather, fetchGatewaySkills, fetchGatewayAgents } from '@/lib/gateway'

interface Props {
  chats: Chat[]
  activeChat: Chat | null
  isStreaming: boolean
  brief: GatewayBrief | null | undefined
  search: GatewaySearchSnapshot | null
  activeModelName: string
}

export function RightBar({ chats, activeChat, isStreaming, brief, search, activeModelName }: Props) {
  const [weather, setWeather] = useState<GatewayWeather | null>(null)
  const [skills, setSkills] = useState<GatewaySkill[]>([])
  const [agents, setAgents] = useState<GatewayAgent[]>([])

  useEffect(() => {
    void fetchGatewayWeather().then(setWeather)
    const id = setInterval(() => { void fetchGatewayWeather().then(setWeather) }, 1800000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    void fetchGatewaySkills().then(setSkills)
    void fetchGatewayAgents().then(setAgents)
  }, [])

  const tokenEstimate = activeChat
    ? Math.round(activeChat.messages.reduce((s, m) => s + m.content.length, 0) / 4)
    : 0

  return (
    <aside style={{
      width: 'var(--rightbar)',
      height: '100vh',
      borderLeft: '1px solid var(--border)',
      background: 'var(--bg-deep)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      {/* Status strip */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}>
        <Label>model</Label>
        <span style={valueStyle}>{activeModelName}</span>
        {weather && (
          <>
            <Label>weather</Label>
            <span style={valueStyle}>
              {weather.description} {weather.temp_c}°C
            </span>
          </>
        )}
      </div>

      {/* Context / search results */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {search && search.results.length > 0 ? (
          <section>
            <Label>context</Label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
              {search.results.slice(0, 4).map((r, i) => (
                <div key={i} style={contextRowStyle}>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {r.source || 'memory'}
                  </span>
                  <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: '3px 0 0', lineHeight: 1.5 }}>
                    {r.text.slice(0, 120)}{r.text.length > 120 ? '…' : ''}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section>
            <Label>context</Label>
            <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6, fontFamily: 'var(--font-mono)' }}>
              send a message to load context
            </p>
          </section>
        )}

        {/* Brief snippet */}
        {brief?.intention && (
          <section>
            <Label>today's intention</Label>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6, lineHeight: 1.6 }}>
              {brief.intention.slice(0, 280)}{brief.intention.length > 280 ? '…' : ''}
            </p>
          </section>
        )}

        {/* Session stats */}
        <section>
          <Label>session</Label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
            <StatRow label="messages" value={String(activeChat?.messages.length ?? 0)} />
            <StatRow label="~tokens" value={tokenEstimate > 0 ? String(tokenEstimate) : '—'} />
            <StatRow label="streaming" value={isStreaming ? 'yes' : 'no'} highlight={isStreaming} />
            <StatRow label="chats" value={String(chats.length)} />
          </div>
        </section>

        {/* Skills */}
        {skills.length > 0 && (
          <section>
            <Label>skills</Label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 6 }}>
              {skills.slice(0, 6).map(s => (
                <span key={s.name} style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  · {s.name}
                </span>
              ))}
              {skills.length > 6 && (
                <span style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                  +{skills.length - 6} more
                </span>
              )}
            </div>
          </section>
        )}

        {/* Agents */}
        {agents.length > 0 && (
          <section>
            <Label>agents</Label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 6 }}>
              {agents.slice(0, 5).map(a => (
                <span key={a.role} style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  · {a.role}
                </span>
              ))}
            </div>
          </section>
        )}
      </div>
    </aside>
  )
}

function Label({ children }: { children: string }) {
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: 'var(--text-muted)',
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
    }}>
      {children}
    </span>
  )
}

function StatRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{label}</span>
      <span style={{ fontSize: 11, color: highlight ? 'var(--purple)' : 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
        {value}
      </span>
    </div>
  )
}

const valueStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)',
}

const contextRowStyle: React.CSSProperties = {
  padding: '8px 10px',
  background: 'var(--bg-card)',
  border: '1px solid var(--border-dim)',
  borderLeft: '3px solid var(--indigo)',
  borderRadius: 6,
}
