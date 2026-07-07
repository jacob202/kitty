'use client'
import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useTodos, useAddTodo, useCompleteTodo, useDeleteTodo } from '@/lib/queries'

export function TodoPanel() {
  const todosQuery = useTodos()
  const addTodo = useAddTodo()
  const completeTodo = useCompleteTodo()
  const deleteTodo = useDeleteTodo()
  const [input, setInput] = useState('')

  const todos = todosQuery.data ?? []
  const adding = addTodo.isPending
  const active = todos.filter(t => t.status === 'pending' || t.status === 'in_progress')
  const done = todos.filter(t => t.status === 'completed')

  function handleAdd() {
    const content = input.trim()
    if (!content || adding) return
    addTodo.mutate(content, {
      onSuccess: result => {
        if (result) setInput('')
      },
    })
  }

  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {active.length > 0 ? (
        <div style={{ display: 'grid', gap: 4 }}>
          {active.map(t => (
            <div key={t.id} style={rowStyle}>
              <button onClick={() => completeTodo.mutate(t.id)} style={checkStyle} title="complete">
                {t.status === 'in_progress' ? '▶' : '☐'}
              </button>
              <span style={{ ...labelStyle, flex: 1 }}>
                {t.content}
                {t.active_form && <em style={activeFormStyle}> — {t.active_form}</em>}
              </span>
              <button onClick={() => deleteTodo.mutate(t.id)} style={removeStyle} title="delete">×</button>
            </div>
          ))}
        </div>
      ) : (
        <p style={emptyStyle}>no todos</p>
      )}

      {done.length > 0 && (
        <p style={{ ...emptyStyle, color: 'var(--ink-2)' }}>
          {done.length} completed
        </p>
      )}

      <div style={{ display: 'flex', gap: 5, marginTop: 2 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="add todo…"
          style={inputStyle}
        />
        <button
          onClick={handleAdd}
          disabled={!input.trim() || adding}
          style={{ ...addBtnStyle, opacity: !input.trim() || adding ? 0.4 : 1 }}
        >
          {adding ? '…' : '+'}
        </button>
      </div>
    </div>
  )
}

const rowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 6px',
  background: 'var(--recessed)',
  border: '1px solid var(--line)',
  borderRadius: 4,
}

const labelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const activeFormStyle: CSSProperties = {
  color: 'var(--ink-2)',
  fontStyle: 'italic',
}

const checkStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--teal)',
  cursor: 'pointer',
  fontSize: 12,
  padding: 0,
  flexShrink: 0,
  lineHeight: 1,
}

const removeStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--ink-2)',
  cursor: 'pointer',
  fontSize: 13,
  padding: '0 2px',
  lineHeight: 1,
  flexShrink: 0,
}

const inputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--recessed)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '4px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  outline: 'none',
  minWidth: 0,
}

const addBtnStyle: CSSProperties = {
  padding: '4px 10px',
  background: 'rgba(78,201,176,0.12)',
  border: '1px solid rgba(78,201,176,0.25)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--teal)',
  cursor: 'pointer',
  flexShrink: 0,
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
  margin: 0,
}
