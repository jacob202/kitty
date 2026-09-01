'use client'

import type { CSSProperties } from 'react'

import { useAgentSessions, useAgentStatus, useStopAgent } from '@/lib/queries'
import type { AgentSession } from '@/lib/gateway'
import { describeFailure } from '@/lib/failure-copy'

export function AgentSessionsPanel({ selectedSessionId, isMobile = false }: { selectedSessionId: number | null; isMobile?: boolean }) {
  const selected = useAgentStatus(selectedSessionId)
  const recent = useAgentSessions(12)
  const stop = useStopAgent()
  const pad = isMobile ? '20px 16px 124px' : '32px 40px 48px'
  const chosen = selected.data ?? (selectedSessionId == null ? recent.data?.[0] : undefined)

  return (
    <div style={{ flex: 1, padding: pad, minWidth: 0, overflowY: 'auto' }}>
      <header style={{ maxWidth: 760, marginBottom: 24 }}>
        <h1 style={titleStyle}>Agent session</h1>
        <p style={subtitleStyle}>The autonomous session behind this activity item.</p>
      </header>

      {selectedSessionId != null && selected.isLoading && <p role="status" style={mutedStyle}>Loading agent session…</p>}
      {selectedSessionId != null && selected.isError && <p role="alert" style={errorStyle}>Couldn’t load this agent session — {describeFailure(selected.error)}</p>}
      {selectedSessionId == null && recent.isLoading && <p role="status" style={mutedStyle}>Loading recent agent sessions…</p>}
      {selectedSessionId == null && recent.isError && <p role="alert" style={errorStyle}>Couldn’t load recent agent sessions — {describeFailure(recent.error)}</p>}

      {chosen ? (
        <AgentSessionCard session={chosen} stopping={stop.isPending} onStop={() => stop.mutate(chosen.session_id)} />
      ) : (!selected.isLoading && !recent.isLoading ? <p style={mutedStyle}>No agent session is selected.</p> : null)}

      {selectedSessionId == null && (recent.data?.length ?? 0) > 1 && (
        <section aria-label="Recent agent sessions" style={{ marginTop: 28, display: 'grid', gap: 8, maxWidth: 760 }}>
          <h2 style={sectionTitleStyle}>Recent sessions</h2>
          {recent.data?.slice(1).map(session => (
            <div key={session.session_id} style={rowStyle}>
              <div style={{ minWidth: 0 }}>
                <div style={rowTitleStyle}>{session.goal || 'Agent session'}</div>
                <div style={metaStyle}>{humanize(session.status)} · session {session.session_id}</div>
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  )
}

function AgentSessionCard({ session, stopping, onStop }: { session: AgentSession; stopping: boolean; onStop: () => void }) {
  const active = session.status === 'active' || session.status === 'running' || session.status === 'queued'
  const output = session.output || session.last_output_snippet
  return (
    <article aria-label={`Agent session ${session.session_id}`} style={cardStyle}>
      <div style={cardHeaderStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={metaStyle}>session {session.session_id} · {humanize(session.status)}</div>
          <h2 style={goalStyle}>{session.goal || 'Agent session'}</h2>
        </div>
        {active && (
          <button type="button" onClick={onStop} disabled={stopping} style={stopStyle}>
            {stopping ? 'Stopping…' : 'Stop agent'}
          </button>
        )}
      </div>
      {typeof session.iterations === 'number' && <div style={metaStyle}>{session.iterations} agent turn{session.iterations === 1 ? '' : 's'}</div>}
      {output ? <pre style={outputStyle}>{output}</pre> : <p style={mutedStyle}>No agent output has been recorded yet.</p>}
    </article>
  )
}

function humanize(value: string): string { return value.replace(/[_-]+/g, ' ') }

const titleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 28, color: 'var(--color-text-primary, var(--ink))' }
const subtitleStyle: CSSProperties = { margin: '6px 0 0', fontSize: 13, color: 'var(--color-text-secondary, var(--ink-2))' }
const cardStyle: CSSProperties = { maxWidth: 760, padding: 18, border: '1px solid var(--color-separator, var(--line))', borderRadius: 12, background: 'var(--color-surface, var(--surface))', display: 'grid', gap: 14 }
const cardHeaderStyle: CSSProperties = { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }
const goalStyle: CSSProperties = { margin: '5px 0 0', fontFamily: 'var(--font-display)', fontSize: 20, lineHeight: 1.3, color: 'var(--color-text-primary, var(--ink))', overflowWrap: 'anywhere' }
const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-text-secondary, var(--ink-2))' }
const outputStyle: CSSProperties = { margin: 0, padding: 14, maxHeight: '48vh', overflow: 'auto', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', borderRadius: 8, background: 'var(--color-background, var(--bg))', border: '1px solid var(--color-separator, var(--line))', fontFamily: 'var(--font-mono)', fontSize: 11, lineHeight: 1.55, color: 'var(--color-text-primary, var(--ink))' }
const stopStyle: CSSProperties = { minHeight: 44, border: '1px solid var(--color-separator, var(--line))', borderRadius: 8, background: 'transparent', color: 'var(--color-destructive)', padding: '8px 12px', fontWeight: 700, cursor: 'pointer', flexShrink: 0 }
const mutedStyle: CSSProperties = { margin: 0, fontSize: 13, color: 'var(--color-text-secondary, var(--ink-2))' }
const errorStyle: CSSProperties = { ...mutedStyle, color: 'var(--color-destructive)' }
const sectionTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--color-text-primary, var(--ink))' }
const rowStyle: CSSProperties = { padding: 12, border: '1px solid var(--color-separator, var(--line))', borderRadius: 9, background: 'var(--color-surface, var(--surface))' }
const rowTitleStyle: CSSProperties = { fontSize: 13, fontWeight: 650, color: 'var(--color-text-primary, var(--ink))', overflowWrap: 'anywhere' }
