'use client'

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import {
  fetchGlobalAgentInbox,
  fetchGlobalAgentMessages,
  fetchGlobalAgentRoom,
  postGlobalAgentMessage,
  updateGlobalAgentReceipt,
  type AgentRoomInboxMessage,
  type AgentWorkspace,
  type AgentWorkspaceMessage,
} from '@/lib/gateway'

const POLL_INTERVAL_MS = 3_000
const CANONICAL_AGENTS = [
  { id: 'chatgpt', name: 'ChatGPT' },
  { id: 'claude', name: 'Claude' },
  { id: 'codex', name: 'Codex' },
  { id: 'kitty', name: 'Kitty' },
] as const

export function AgentWorkspacePanel() {
  const [room, setRoom] = useState<AgentWorkspace | null>(null)
  const [messages, setMessages] = useState<AgentWorkspaceMessage[]>([])
  const [inbox, setInbox] = useState<AgentRoomInboxMessage[]>([])
  const [recipientId, setRecipientId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [replyTarget, setReplyTarget] = useState<AgentWorkspaceMessage | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)
  const pollInFlight = useRef(false)

  const unreadIds = useMemo(
    () => new Set(inbox.filter((item) => item.seen_at === null).map((item) => item.id)),
    [inbox],
  )
  const acknowledgedIds = useMemo(
    () => new Set(inbox.filter((item) => item.acknowledged_at !== null).map((item) => item.id)),
    [inbox],
  )
  const unreadCount = unreadIds.size
  const messageById = useMemo(() => new Map(messages.map((message) => [message.id, message])), [messages])

  useEffect(() => {
    mounted.current = true
    void loadInitial()
    const intervalId = window.setInterval(() => void pollRoom(), POLL_INTERVAL_MS)
    return () => {
      mounted.current = false
      window.clearInterval(intervalId)
    }
  }, [])

  async function loadInitial() {
    setLoading(true)
    try {
      const [loadedRoom, recent, jacobInbox] = await Promise.all([
        fetchGlobalAgentRoom(),
        fetchGlobalAgentMessages(100),
        fetchGlobalAgentInbox(false, 100),
      ])
      if (!mounted.current) return
      setRoom(loadedRoom)
      setMessages(recent)
      setInbox(jacobInbox)
      setError(null)
    } catch (err) {
      if (mounted.current) setError(errorMessage(err, 'Could not load the Global Agent Room'))
    } finally {
      if (mounted.current) setLoading(false)
    }
  }

  async function pollRoom() {
    if (pollInFlight.current) return
    pollInFlight.current = true
    try {
      const [recent, jacobInbox] = await Promise.all([
        fetchGlobalAgentMessages(100),
        fetchGlobalAgentInbox(false, 100),
      ])
      if (!mounted.current) return
      setMessages(recent)
      setInbox(jacobInbox)
      setError(null)
    } catch (err) {
      // Polling is recovery-only: never erase the last durable transcript.
      if (mounted.current) setError(errorMessage(err, 'Could not refresh the Global Agent Room'))
    } finally {
      pollInFlight.current = false
    }
  }

  function beginReply(message: AgentWorkspaceMessage) {
    setReplyTarget(message)
    if (message.sender_id !== 'jacob') setRecipientId(message.sender_id)
  }

  async function handleSend() {
    const content = draft.trim()
    if (!content || sending) return
    setSending(true)
    setError(null)
    try {
      const posted = await postGlobalAgentMessage({
        recipientId,
        content,
        messageKind: 'prompt',
        parentMessageId: replyTarget?.id ?? null,
      })
      if (!mounted.current) return
      setMessages((current) => current.some((item) => item.id === posted.id) ? current : [...current, posted])
      setDraft('')
      setReplyTarget(null)
      await pollRoom()
    } catch (err) {
      // A failed post is not accepted: keep both the user's draft and thread target intact.
      if (mounted.current) setError(errorMessage(err, 'Could not send the message'))
    } finally {
      if (mounted.current) setSending(false)
    }
  }

  async function handleAcknowledge(message: AgentWorkspaceMessage) {
    if (acknowledgingId) return
    setAcknowledgingId(message.id)
    setError(null)
    try {
      const receipt = await updateGlobalAgentReceipt(message.id, 'acknowledged')
      if (!mounted.current) return
      setInbox((current) => current.map((item) => item.id === message.id ? {
        ...item,
        seen_at: receipt.seen_at,
        acknowledged_at: receipt.acknowledged_at,
        receipt_state: receipt.receipt_state,
      } : item))
    } catch (err) {
      if (mounted.current) setError(errorMessage(err, 'Could not acknowledge the message'))
    } finally {
      if (mounted.current) setAcknowledgingId(null)
    }
  }

  return (
    <div style={shellStyle}>
      <header style={headerStyle}>
        <div>
          <p style={eyebrowStyle}>agents · command center</p>
          <h1 style={titleStyle}>Global Agent Room</h1>
          <p style={subtitleStyle}>Jacob, Kitty, and your coding agents share one durable conversation.</p>
        </div>
        <div style={truthStripStyle} aria-label="Room state">
          <span style={truthPillStyle}>durable room</span>
          <span style={truthPillStyle}>four registered agents</span>
          <span style={unreadPillStyle}>{unreadCount} unread</span>
        </div>
      </header>

      {loading && !room && <p style={mutedStyle}>Loading durable room…</p>}

      <Card padding="md" ariaLabel="Registered agents" style={sectionStyle}>
        <div style={sectionHeadingRowStyle}>
          <div>
            <h2 style={sectionTitleStyle}>Registered agents</h2>
            <p style={sectionNoteStyle}>Membership only. No live presence is inferred.</p>
          </div>
          <span style={tinyMetaStyle}>workspace_global</span>
        </div>
        <div style={rosterStyle}>
          {CANONICAL_AGENTS.map((agent) => (
            <div key={agent.id} style={agentCardStyle}>
              <span style={agentAvatarStyle}>{agent.name.slice(0, 1)}</span>
              <span style={{ minWidth: 0 }}>
                <strong style={agentNameStyle}>{agent.name}</strong>
                <span style={registeredStyle}>registered</span>
              </span>
            </div>
          ))}
        </div>
      </Card>

      <Card padding="md" ariaLabel="Global Agent Room transcript" style={sectionStyle}>
        <div style={sectionHeadingRowStyle}>
          <div>
            <h2 style={sectionTitleStyle}>Room transcript</h2>
            <p style={sectionNoteStyle}>Broadcasts, direct messages, and replies share the same durable history.</p>
          </div>
          {unreadCount > 0 && <span style={attentionStyle}>{unreadCount} need attention</span>}
        </div>

        <div style={transcriptStyle} aria-live="polite">
          {!loading && messages.length === 0 && <p style={mutedStyle}>No messages yet.</p>}
          {messages.map((message) => {
            const parent = message.parent_message_id ? messageById.get(message.parent_message_id) : null
            const senderName = displayName(message.sender_id)
            const isJacob = message.sender_id === 'jacob'
            const canAcknowledge = !isJacob && unreadIds.has(message.id) && !acknowledgedIds.has(message.id)
            return (
              <article key={message.id} style={messageStyle(isJacob)}>
                <div style={messageMetaStyle}>
                  <strong style={{ color: 'var(--ink)' }}>{senderName}</strong>
                  <span>{message.message_kind}</span>
                  <span>{message.recipient_id ? `→ ${displayName(message.recipient_id)}` : '→ room'}</span>
                </div>
                {parent && <p style={replyTrailStyle}>Reply to {displayName(parent.sender_id)} · {truncate(parent.content, 72)}</p>}
                <p style={messageBodyStyle}>{message.content}</p>
                <div style={messageActionsStyle}>
                  {!isJacob && (
                    <Button size="sm" variant="ghost" onClick={() => beginReply(message)} ariaLabel={`Reply to ${senderName}`}>
                      Reply
                    </Button>
                  )}
                  {canAcknowledge && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => void handleAcknowledge(message)}
                      loading={acknowledgingId === message.id}
                      ariaLabel={`Acknowledge message from ${senderName}`}
                    >
                      Acknowledge
                    </Button>
                  )}
                  {acknowledgedIds.has(message.id) && <span style={ackStyle}>acknowledged</span>}
                </div>
              </article>
            )
          })}
        </div>

        <div style={composerStyle}>
          {replyTarget && (
            <div style={replyContextStyle}>
              <span><strong>Replying to {displayName(replyTarget.sender_id)}</strong> · {truncate(replyTarget.content, 88)}</span>
              <Button size="sm" variant="ghost" onClick={() => setReplyTarget(null)} ariaLabel="Cancel reply">Cancel</Button>
            </div>
          )}
          <div style={composerControlsStyle}>
            <label style={recipientLabelStyle}>
              <span>Recipient</span>
              <select
                aria-label="Recipient"
                value={recipientId ?? ''}
                onChange={(event) => setRecipientId(event.target.value || null)}
                style={selectStyle}
              >
                <option value="">Room · broadcast</option>
                {CANONICAL_AGENTS.map((agent) => <option key={agent.id} value={agent.id}>Direct · {agent.name}</option>)}
              </select>
            </label>
            <span style={composerTruthStyle}>Posting as Jacob</span>
          </div>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void handleSend()
              }
            }}
            placeholder="Message the room or an agent…"
            rows={4}
            style={textareaStyle}
          />
          <div style={composerFooterStyle}>
            <span style={composerTruthStyle}>Enter to send · Shift+Enter for a new line</span>
            <Button onClick={() => void handleSend()} disabled={!draft.trim()} loading={sending}>Send message</Button>
          </div>
        </div>
      </Card>

      {error && <p role="alert" style={errorStyle}>{error}</p>}
    </div>
  )
}

function displayName(id: string): string {
  if (id === 'jacob') return 'Jacob'
  return CANONICAL_AGENTS.find((agent) => agent.id === id)?.name ?? id
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

const shellStyle: CSSProperties = { flex: 1, minWidth: 0, width: '100%', boxSizing: 'border-box', padding: 'clamp(16px, 3vw, 32px)', display: 'grid', alignContent: 'start', gap: 16, overflowX: 'hidden' }
const headerStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: 14 }
const eyebrowStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.12em', color: 'var(--c-purple)', textTransform: 'uppercase' }
const titleStyle: CSSProperties = { margin: '5px 0 0', fontFamily: 'var(--font-display)', fontSize: 'clamp(26px, 4vw, 36px)', lineHeight: 1.08, color: 'var(--ink)' }
const subtitleStyle: CSSProperties = { margin: '7px 0 0', maxWidth: 680, color: 'var(--ink-2)', lineHeight: 1.5 }
const truthStripStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 6 }
const truthPillStyle: CSSProperties = { padding: '5px 8px', borderRadius: 999, border: '1px solid var(--line)', background: 'var(--surface-2)', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', whiteSpace: 'nowrap' }
const unreadPillStyle: CSSProperties = { ...truthPillStyle, color: 'var(--c-purple)', borderColor: 'color-mix(in srgb, var(--c-purple) 45%, var(--line))' }
const sectionStyle: CSSProperties = { display: 'grid', gap: 14, minWidth: 0 }
const sectionHeadingRowStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--ink)' }
const sectionNoteStyle: CSSProperties = { margin: '4px 0 0', color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.45 }
const tinyMetaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const rosterStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 170px), 1fr))', gap: 8 }
const agentCardStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 9, minWidth: 0, padding: '9px 10px', borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface-2)' }
const agentAvatarStyle: CSSProperties = { display: 'grid', placeItems: 'center', width: 30, height: 30, flex: '0 0 30px', borderRadius: 9, background: 'color-mix(in srgb, var(--c-purple) 12%, var(--surface))', color: 'var(--c-purple)', fontFamily: 'var(--font-display)', fontWeight: 700 }
const agentNameStyle: CSSProperties = { display: 'block', fontSize: 13, color: 'var(--ink)' }
const registeredStyle: CSSProperties = { display: 'block', marginTop: 2, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const attentionStyle: CSSProperties = { ...truthPillStyle, color: 'var(--c-yellow)' }
const transcriptStyle: CSSProperties = { display: 'grid', gap: 8, maxHeight: 'min(52vh, 560px)', overflowY: 'auto', overflowX: 'hidden', paddingRight: 2 }
const messageStyle = (isJacob: boolean): CSSProperties => ({ padding: '10px 12px', minWidth: 0, borderRadius: 10, border: '1px solid var(--line)', background: isJacob ? 'color-mix(in srgb, var(--c-purple) 8%, var(--surface))' : 'var(--surface-2)' })
const messageMetaStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: '4px 8px', alignItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const replyTrailStyle: CSSProperties = { margin: '7px 0 0', paddingLeft: 8, borderLeft: '2px solid var(--line)', color: 'var(--ink-2)', fontSize: 11, lineHeight: 1.35, overflowWrap: 'anywhere' }
const messageBodyStyle: CSSProperties = { margin: '7px 0 0', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', color: 'var(--ink)', fontSize: 14, lineHeight: 1.5 }
const messageActionsStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4, marginTop: 6 }
const ackStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const composerStyle: CSSProperties = { display: 'grid', gap: 9, paddingTop: 2, borderTop: '1px solid var(--line)' }
const replyContextStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginTop: 10, padding: '7px 9px', borderRadius: 8, background: 'var(--surface-2)', color: 'var(--ink-2)', fontSize: 12, overflowWrap: 'anywhere' }
const composerControlsStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8, marginTop: 10 }
const recipientLabelStyle: CSSProperties = { display: 'grid', gap: 4, minWidth: 'min(100%, 220px)', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const selectStyle: CSSProperties = { width: '100%', minHeight: 38, padding: '7px 9px', borderRadius: 8, border: '1px solid var(--line)', background: 'var(--surface-2)', color: 'var(--ink)', fontFamily: 'var(--font-body)' }
const composerTruthStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const textareaStyle: CSSProperties = { width: '100%', minWidth: 0, resize: 'vertical', boxSizing: 'border-box', padding: 11, borderRadius: 9, border: '1px solid var(--line)', background: 'var(--surface-2)', color: 'var(--ink)', fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: 1.45 }
const composerFooterStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 8 }
const mutedStyle: CSSProperties = { margin: 0, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 11 }
const errorStyle: CSSProperties = { margin: 0, padding: '8px 10px', borderRadius: 8, border: '1px solid color-mix(in srgb, var(--cat-ginger) 45%, var(--line))', background: 'var(--surface)', color: 'var(--cat-ginger)', fontFamily: 'var(--font-mono)', fontSize: 11, overflowWrap: 'anywhere' }
