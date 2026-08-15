'use client'

import { useEffect, useRef, useState } from 'react'
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
  const [workspaceMissing, setWorkspaceMissing] = useState(false)
  const loadInFlight = useRef<Promise<void> | null>(null)

  useEffect(() => {
    const storedId = window.localStorage.getItem(STORAGE_KEY)
    setWorkspaceId(storedId)
    if (!storedId) {
      setLoading(false)
      return
    }
    void loadWorkspace(storedId)
  }, [])

  const hasRunningTurn = workspace?.turns.some((turn) => turn.status === 'running') ?? false

  useEffect(() => {
    if (!workspaceId || !hasRunningTurn) return
    const intervalId = window.setInterval(() => void loadWorkspace(workspaceId, false), 1_000)
    return () => window.clearInterval(intervalId)
  }, [workspaceId, hasRunningTurn])

  async function loadWorkspace(id: string, showLoading = true) {
    if (loadInFlight.current) {
      await loadInFlight.current
      return
    }
    const request = (async () => {
      if (showLoading) setLoading(true)
      try {
        const loaded = await fetchAgentWorkspace(id)
        setWorkspace(loaded)
        setWorkspaceMissing(false)
        setError(null)
      } catch (err) {
        // A definitively-missing workspace (e.g. after a local DB reset) 404s
        // forever; retrying the same id can't recover it, so surface a reset
        // path instead of trapping the user in an unusable "retry" loop.
        const message = err instanceof Error ? err.message : 'Could not load the shared workspace'
        if (message.includes('404')) {
          setWorkspaceMissing(true)
        } else {
          // A transient poll failure must not erase the last durable transcript.
          setError(message)
        }
      } finally {
        if (showLoading) setLoading(false)
      }
    })()
    loadInFlight.current = request
    try {
      await request
    } finally {
      if (loadInFlight.current === request) loadInFlight.current = null
    }
  }

  function resetWorkspace() {
    window.localStorage.removeItem(STORAGE_KEY)
    setWorkspaceId(null)
    setWorkspace(null)
    setWorkspaceMissing(false)
    setError(null)
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
    if (!message || !workspaceId || busy || hasRunningTurn) return
    setBusy(true)
    setError(null)
    try {
      const result = await runAgentWorkspaceTurn(workspaceId, message)
      setWorkspace((current) => current ? {
        ...current,
        turns: [result.turn, ...current.turns.filter((turn) => turn.id !== result.turn.id)],
        updated_at: Date.now() / 1000,
      } : current)
      setDraft('')
      await loadWorkspace(workspaceId, false)
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

      {!loading && !workspace && !workspaceId && (
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

      {!loading && !workspace && workspaceId && !workspaceMissing && (
        <section style={cardStyle}>
          <h2 style={sectionTitleStyle}>Reopen your shared room</h2>
          <p style={bodyStyle}>
            The saved room could not be reached. Retry before creating another room.
          </p>
          <button type="button" onClick={() => void loadWorkspace(workspaceId)} disabled={busy} style={buttonStyle}>
            retry room
          </button>
          <button type="button" onClick={resetWorkspace} disabled={busy} style={buttonStyle}>
            start a new room
          </button>
        </section>
      )}

      {!loading && !workspace && workspaceId && workspaceMissing && (
        <section style={cardStyle}>
          <h2 style={sectionTitleStyle}>This room no longer exists</h2>
          <p style={bodyStyle}>
            The saved room was not found — it may have been cleared. Start a new one to continue.
          </p>
          <button type="button" onClick={resetWorkspace} disabled={busy} style={buttonStyle}>
            start a new room
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
                  <span style={dotStyle(agent.id === workspace.turns.find((turn) => turn.status === 'running')?.active_agent_id)} />
                  {agent.display_name}
                </span>
              ))}
            </div>
          </section>

          {workspace.turns[0] && (
            <section style={turnStyle(workspace.turns[0].status)}>
              <div style={messageMetaStyle}>
                <strong>turn</strong>
                <span>{workspace.turns[0].status}</span>
              </div>
              {workspace.turns[0].status === 'running' && (
                <p style={messageBodyStyle}>
                  {workspace.turns[0].active_agent_id ?? 'room'} is working. Partial messages are saved as they arrive.
                </p>
              )}
              {workspace.turns[0].status !== 'running' && workspace.turns[0].error_message && (
                <p style={messageBodyStyle}>
                  Incomplete: {workspace.turns[0].error_type ?? 'agent failure'} — {workspace.turns[0].error_message}
                </p>
              )}
            </section>
          )}

          <section style={cardStyle}>
            <h2 style={sectionTitleStyle}>Room transcript</h2>
            <div style={transcriptStyle}>
              {workspace.messages.length === 0 && <p style={mutedStyle}>No messages yet.</p>}
              {workspace.messages.map((message) => (
                <article key={message.id} style={messageStyle(message)}>
                  <div style={messageMetaStyle}>
                    <strong>{message.sender_id}</strong>
                    <span>{messageLabel(message)}</span>
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
              <button type="button" onClick={() => void handleSend()} disabled={busy || hasRunningTurn || !draft.trim()} style={buttonStyle}>
                {busy || hasRunningTurn ? 'working…' : 'send to room'}
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
const dotStyle = (active: boolean) => ({ width: 6, height: 6, borderRadius: '50%', background: active ? 'var(--c-purple)' : 'var(--c-blue)' })
const transcriptStyle = { display: 'grid', gap: 8, maxHeight: 460, overflowY: 'auto' as const }
const messageStyle = (message: AgentWorkspace['messages'][number]) => ({
  padding: '9px 10px',
  background: message.sender_kind === 'user' ? 'rgba(102,119,204,0.08)' : 'var(--surface-2)',
  borderRadius: 8,
  border: `1px solid ${message.sender_kind === 'system' ? 'rgba(204,102,88,0.55)' : 'var(--line)'}`,
})
const turnStyle = (status: AgentWorkspace['turns'][number]['status']) => ({
  ...cardStyle,
  borderColor: status === 'failed' || status === 'interrupted' ? 'rgba(204,102,88,0.65)' : 'var(--line)',
})
const messageMetaStyle = { display: 'flex', gap: 8, alignItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const messageBodyStyle = { margin: '5px 0 0', whiteSpace: 'pre-wrap' as const, color: 'var(--ink)', lineHeight: 1.5 }
const composerStyle = { display: 'grid', gap: 8 }
const textareaStyle = { width: '100%', resize: 'vertical' as const, boxSizing: 'border-box' as const, padding: 10, borderRadius: 8, border: '1px solid var(--line)', background: 'var(--surface-2)', color: 'var(--ink)', fontFamily: 'var(--font-body)', lineHeight: 1.4 }
const buttonStyle = { justifySelf: 'start', padding: '8px 12px', borderRadius: 7, border: '1px solid rgba(102,119,204,0.4)', background: 'rgba(102,119,204,0.14)', color: 'var(--c-purple)', fontFamily: 'var(--font-mono)', fontSize: 11, cursor: 'pointer' }
const mutedStyle = { margin: 0, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 11 }
const errorStyle = { margin: 0, color: 'var(--cat-ginger)', fontFamily: 'var(--font-mono)', fontSize: 11 }

function messageLabel(message: AgentWorkspace['messages'][number]): string {
  if (message.sender_id === 'builder' && message.message_kind === 'handoff') return 'builder proposal'
  if (message.sender_kind === 'system' && message.message_kind === 'status') return 'failure status'
  return message.message_kind
}
