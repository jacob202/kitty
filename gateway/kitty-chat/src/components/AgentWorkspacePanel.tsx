'use client'

import { useEffect, useState } from 'react'
import {
  createAgentWorkspace,
  fetchAgentWorkspace,
  runAgentWorkspaceTurn,
  type AgentWorkspace,
} from '@/lib/gateway'

const STORAGE_KEY = 'kitty.agent-workspace-id'

export function AgentWorkspacePanel() {
  const [workspace, setWorkspace] = useState<AgentWorkspace | null>(null)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const storedId = window.localStorage.getItem(STORAGE_KEY)
    setWorkspaceId(storedId)
    if (!storedId) {
      setLoading(false)
      return
    }
    void loadWorkspace(storedId)
  }, [])

  async function loadWorkspace(id: string) {
    setLoading(true)
    setError(null)
    try {
      setWorkspace(await fetchAgentWorkspace(id))
    } catch (err) {
      setWorkspace(null)
      setError(err instanceof Error ? err.message : 'Could not load the shared workspace')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    setBusy(true)
    setError(null)
    try {
      const created = await createAgentWorkspace('Kitty Shared Room', 'Coordinate a verified outcome with dedicated agents.')
      window.localStorage.setItem(STORAGE_KEY, created.id)
      setWorkspaceId(created.id)
      setWorkspace(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the shared workspace')
    } finally {
      setBusy(false)
      setLoading(false)
    }
  }

  async function handleSend() {
    const message = draft.trim()
    if (!message || !workspaceId || busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await runAgentWorkspaceTurn(workspaceId, message)
      setWorkspace((current) => current ? {
        ...current,
        messages: result.messages,
        events: result.events,
        updated_at: Date.now() / 1000,
      } : current)
      setDraft('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The agent handoff failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={shellStyle}>
      <header>
        <p style={eyebrowStyle}>shared agent workspace</p>
        <h1 style={titleStyle}>Agents that work in the same room</h1>
        <p style={subtitleStyle}>
          Planner, Researcher, Builder, and Reviewer share durable messages and handoffs.
          Builder execution still belongs to KittyBuilder.
        </p>
      </header>

      {loading && <p style={mutedStyle}>loading room…</p>}

      {!loading && !workspace && (
        <section style={cardStyle}>
          <h2 style={sectionTitleStyle}>Create your first room</h2>
          <p style={bodyStyle}>
            This creates one durable local workspace. Nothing runs until you send a request.
          </p>
          <button type="button" onClick={() => void handleCreate()} disabled={busy} style={buttonStyle}>
            {busy ? 'creating…' : 'create shared room'}
          </button>
        </section>
      )}

      {!loading && workspace && (
        <>
          <section style={cardStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>{workspace.name}</h2>
                <p style={bodyStyle}>{workspace.objective}</p>
              </div>
              <span style={statusStyle}>{workspace.status}</span>
            </div>
            <div style={rosterStyle}>
              {workspace.agents.map((agent) => (
                <span key={agent.id} style={agentChipStyle}>
                  <span style={dotStyle} />{agent.display_name}
                </span>
              ))}
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={sectionTitleStyle}>Room transcript</h2>
            <div style={transcriptStyle}>
              {workspace.messages.length === 0 && <p style={mutedStyle}>No messages yet.</p>}
              {workspace.messages.map((message) => (
                <article key={message.id} style={messageStyle}>
                  <div style={messageMetaStyle}>
                    <strong>{message.sender_id}</strong>
                    <span>{message.message_kind}</span>
                    {message.recipient_id && <span>→ {message.recipient_id}</span>}
                  </div>
                  <p style={messageBodyStyle}>{message.content}</p>
                </article>
              ))}
            </div>
            <div style={composerStyle}>
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void handleSend()
                  }
                }}
                placeholder="Ask the room to plan, research, and review…"
                rows={3}
                style={textareaStyle}
              />
              <button type="button" onClick={() => void handleSend()} disabled={busy || !draft.trim()} style={buttonStyle}>
                {busy ? 'working…' : 'send to room'}
              </button>
            </div>
          </section>
        </>
      )}

      {error && <p role="alert" style={errorStyle}>{error}</p>}
    </div>
  )
}

const shellStyle = { flex: 1, padding: '24px 32px 40px', display: 'grid', gap: 18, minWidth: 0 }
const eyebrowStyle = { margin: 0, fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.12em', textTransform: 'lowercase' as const, color: 'var(--c-purple)' }
const titleStyle = { margin: '4px 0 0', fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }
const subtitleStyle = { margin: '6px 0 0', maxWidth: 680, color: 'var(--ink-2)', lineHeight: 1.5 }
const cardStyle = { background: 'var(--surface)', border: '1.5px solid var(--line)', borderRadius: 14, padding: 18, display: 'grid', gap: 12 }
const sectionHeaderStyle = { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }
const sectionTitleStyle = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--ink)' }
const bodyStyle = { margin: '4px 0 0', color: 'var(--ink-2)', lineHeight: 1.5 }
const statusStyle = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-blue)', textTransform: 'lowercase' as const }
const rosterStyle = { display: 'flex', flexWrap: 'wrap' as const, gap: 6 }
const agentChipStyle = { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 8px', borderRadius: 999, background: 'var(--surface-2)', border: '1px solid var(--line)', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }
const dotStyle = { width: 6, height: 6, borderRadius: '50%', background: 'var(--c-blue)' }
const transcriptStyle = { display: 'grid', gap: 8, maxHeight: 460, overflowY: 'auto' as const }
const messageStyle = { padding: '9px 10px', background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--line)' }
const messageMetaStyle = { display: 'flex', gap: 8, alignItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const messageBodyStyle = { margin: '5px 0 0', whiteSpace: 'pre-wrap' as const, color: 'var(--ink)', lineHeight: 1.5 }
const composerStyle = { display: 'grid', gap: 8 }
const textareaStyle = { width: '100%', resize: 'vertical' as const, boxSizing: 'border-box' as const, padding: 10, borderRadius: 8, border: '1px solid var(--line)', background: 'var(--surface-2)', color: 'var(--ink)', fontFamily: 'var(--font-body)', lineHeight: 1.4 }
const buttonStyle = { justifySelf: 'start', padding: '8px 12px', borderRadius: 7, border: '1px solid rgba(102,119,204,0.4)', background: 'rgba(102,119,204,0.14)', color: 'var(--c-purple)', fontFamily: 'var(--font-mono)', fontSize: 11, cursor: 'pointer' }
const mutedStyle = { margin: 0, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 11 }
const errorStyle = { margin: 0, color: 'var(--cat-ginger)', fontFamily: 'var(--font-mono)', fontSize: 11 }
