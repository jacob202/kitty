'use client'
import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { fetchGatewayTodos, addGatewayTodo, completeGatewayTodo, deleteGatewayTodo, type GatewayTodo } from '@/lib/gateway'

export function TodoPanel() {
  const [todos, setTodos] = useState<GatewayTodo[]>([])
  const [input, setInput] = useState('')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    setTodos(await fetchGatewayTodos())
  }

  async function handleAdd() {
    const content = input.trim()
    if (!content || adding) return
    setAdding(true)
    const todo = await addGatewayTodo(content)
    setAdding(false)
    if (todo) {
      setInput('')
      await load()
    }
  }

  async function handleComplete(id: number) {
    await completeGatewayTodo(id)
    await load()
  }

  async function handleDelete(id: number) {
    await deleteGatewayTodo(id)
    await load()
  }

  const active = todos.filter(t => t.status === 'pending' || t.status === 'in_progress')
  const done = todos.filter(t => t.status === 'completed')

  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {active.length > 0 ? (
        <div style={{ display: 'grid', gap: 4 }}>
          {active.map(t => (
            <div key={t.id} style={rowStyle}>
              <button onClick={() => void handleComplete(t.id)} style={checkStyle} title="complete">
                {t.status === 'in_progress' ? '▶' : '☐'}
              </button>
              <span style={{ ...labelStyle, flex: 1 }}>
                {t.content}
                {t.active_form && <em style={activeFormStyle}> — {t.active_form}</em>}
              </span>
              <button onClick={() => void handleDelete(t.id)} style={removeStyle} title="delete">×</button>
            </div>
          ))}
        </div>
      ) : (
        <p style={emptyStyle}>no todos</p>
      )}

      {done.length > 0 && (
        <p style={{ ...emptyStyle, color: 'var(--text-faint)' }}>
          {done.length} completed
        </p>
      )}

      <div style={{ display: 'flex', gap: 5, marginTop: 2 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && void handleAdd()}
          placeholder="add todo…"
          style={inputStyle}
        />
        <button
          onClick={() => void handleAdd()}
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
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
}

const labelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const activeFormStyle: CSSProperties = {
  color: 'var(--text-muted)',
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
  color: 'var(--text-faint)',
  cursor: 'pointer',
  fontSize: 13,
  padding: '0 2px',
  lineHeight: 1,
  flexShrink: 0,
}

const inputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  padding: '4px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
  minWidth: 0,
}

const addBtnStyle: CSSProperties = {
  padding: '4px 10px',
  background: 'rgba(78,201,176,0.12)',
  border: '1px solid rgba(78,201,176,0.25)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--teal)',
  cursor: 'pointer',
  flexShrink: 0,
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
  margin: 0,
}
