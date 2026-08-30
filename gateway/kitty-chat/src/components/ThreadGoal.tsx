'use client'
import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'
import { Chat } from '@/lib/types'
import { patchChatObjective, OBJECTIVE_MAX_LENGTH } from '@/lib/gateway'

interface Props {
  chat: Chat | null
  compact?: boolean
  /** Fold the server-confirmed objective back into canonical chat state. */
  onObjectiveSaved: (chatId: string, objective: string | null) => void
  /**
   * Persist a chat that has never been saved so its objective has a row to
   * PATCH against. Resolves false when persistence failed.
   */
  onEnsurePersisted: (chat: Chat) => Promise<boolean>
}

/**
 * Slim header strip showing the active thread's goal (CR-02). Resting state is
 * one tappable line; tapping expands the strip in place into an inline editor.
 * Persistence is server-confirmed: chat state only changes with the PATCH
 * response, so a rejected save can never masquerade as a saved goal.
 */
export function ThreadGoal({ chat, compact = false, onObjectiveSaved, onEnsurePersisted }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped on chat switch, editor close, and each save: an in-flight response
  // with a stale seq may still report truth via onObjectiveSaved (it is keyed
  // by chat id), but must not touch this component's editor state.
  const seqRef = useRef(0)
  const chatId = chat?.id

  useEffect(() => {
    // A draft belongs to one thread; never let it bleed into the next.
    seqRef.current++
    setEditing(false)
    setDraft('')
    setSaving(false)
    setError(null)
  }, [chatId])

  if (!chat) return null
  const goal = chat.objective ?? null

  const openEditor = () => {
    setDraft(goal ?? '')
    setError(null)
    setEditing(true)
  }

  const closeEditor = () => {
    seqRef.current++
    setEditing(false)
    setDraft('')
    setSaving(false)
    setError(null)
  }

  const save = async (value: string | null) => {
    if (saving) return
    const trimmed = typeof value === 'string' ? value.trim() : null
    const next = trimmed === '' ? null : trimmed
    if (next === goal) {
      closeEditor()
      return
    }
    const seq = ++seqRef.current
    const target = chat
    setSaving(true)
    setError(null)
    try {
      let result: { objective: string | null }
      try {
        result = await patchChatObjective(target.id, next)
      } catch (err) {
        // A chat that has never been persisted has no row to PATCH — save the
        // chat first, then retry once.
        if (!(err instanceof Error && err.message.includes('404'))) throw err
        if (!(await onEnsurePersisted(target))) throw err
        result = await patchChatObjective(target.id, next)
      }
      onObjectiveSaved(target.id, result.objective)
      if (seqRef.current === seq) {
        setEditing(false)
        setDraft('')
        setSaving(false)
      }
    } catch (err) {
      if (seqRef.current === seq) {
        setSaving(false)
        setError(err instanceof Error ? err.message : String(err))
      }
    }
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void save(draft)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      closeEditor()
    }
  }

  const padX = compact ? 16 : 26

  if (!editing) {
    if (goal === null) {
      return (
        <div style={{ ...stripStyle, padding: `0 ${padX}px` }}>
          <button
            onClick={openEditor}
            aria-label="Set thread goal"
            style={{ ...restingBtnStyle, color: 'var(--ink-2)' }}
          >
            ＋ set goal
          </button>
        </div>
      )
    }
    return (
      <div style={{ ...stripStyle, padding: `0 ${padX}px` }}>
        <button
          onClick={openEditor}
          aria-label={`Edit thread goal: ${goal}`}
          title={goal}
          style={{ ...restingBtnStyle, width: '100%', color: 'var(--ink)' }}
        >
          <span aria-hidden="true" style={{ color: 'var(--ink-2)', flexShrink: 0 }}>◎</span>
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              textAlign: 'left',
            }}
          >
            {goal}
          </span>
        </button>
      </div>
    )
  }

  return (
    <div
      style={{
        ...stripStyle,
        minHeight: 0,
        flexDirection: 'column',
        alignItems: 'stretch',
        gap: 8,
        padding: `10px ${padX}px 12px`,
      }}
    >
      <textarea
        aria-label="Thread goal"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKey}
        maxLength={OBJECTIVE_MAX_LENGTH}
        rows={2}
        autoFocus
        disabled={saving}
        placeholder="what's this thread for?"
        style={{
          fontFamily: 'var(--font-body)',
          fontSize: 13,
          lineHeight: 1.5,
          color: 'var(--ink)',
          background: 'var(--bg)',
          border: '1.5px solid var(--line)',
          borderRadius: 10,
          padding: '8px 10px',
          resize: 'none',
          outline: 'none',
          width: '100%',
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {goal !== null && (
          <button
            onClick={() => void save(null)}
            disabled={saving}
            aria-label="Clear thread goal"
            style={{ ...editorBtnStyle, color: 'var(--c-red)' }}
          >
            clear
          </button>
        )}
        <span style={{ flex: 1, minWidth: 0 }}>
          {draft.length >= OBJECTIVE_MAX_LENGTH - 60 && (
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: draft.length >= OBJECTIVE_MAX_LENGTH ? 'var(--c-red)' : 'var(--ink-2)',
              }}
            >
              {draft.length}/{OBJECTIVE_MAX_LENGTH}
            </span>
          )}
        </span>
        <button onClick={closeEditor} aria-label="Cancel goal edit" style={editorBtnStyle}>
          cancel
        </button>
        <button
          onClick={() => void save(draft)}
          disabled={saving}
          aria-label="Save thread goal"
          style={{ ...editorBtnStyle, color: 'var(--ink)', borderColor: 'var(--ink-2)' }}
        >
          {saving ? 'saving…' : 'save'}
        </button>
      </div>
      {error && (
        <div
          role="alert"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-red)' }}
        >
          goal not saved — {error}
        </div>
      )}
    </div>
  )
}

const stripStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  minHeight: 34,
  borderBottom: '1px solid var(--line)',
  background: 'var(--surface)',
  flexShrink: 0,
}

const restingBtnStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 7,
  minHeight: 34,
  maxWidth: '100%',
  padding: 0,
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
}

const editorBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  border: '1.5px solid var(--line)',
  borderRadius: 8,
  padding: '6px 14px',
  background: 'transparent',
  cursor: 'pointer',
  flexShrink: 0,
}
