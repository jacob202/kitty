'use client'
import { useState } from 'react'
import { useTodos, useAddTodo, useCompleteTodo, useDeleteTodo } from '@/lib/queries'
import { Button } from '@/components/ui/Button'
import { WorkCard } from '@/components/shared/WorkCard'
import { Plus } from 'lucide-react'

export function TodoPanel() {
  const todosQuery = useTodos()
  const addTodo = useAddTodo()
  const completeTodo = useCompleteTodo()
  const deleteTodo = useDeleteTodo()
  const [input, setInput] = useState('')
  const [clearDoneError, setClearDoneError] = useState(false)
  const [clearingDone, setClearingDone] = useState(false)

  if (todosQuery.isPending) return <p style={noticeStyle}>loading todos…</p>
  if (todosQuery.isError) return (
    <div style={{ display: 'grid', gap: 8 }}>
      <p style={noticeStyle}>Todos are unavailable right now.</p>
      <button type="button" onClick={() => void todosQuery.refetch()} style={retryStyle}>retry todos</button>
    </div>
  )

  const todos = todosQuery.data ?? []
  const active = todos.filter(t => t.status === 'pending' || t.status === 'in_progress')
  const done = todos.filter(t => t.status === 'completed')

  function handleAdd() {
    const content = input.trim()
    if (!content || addTodo.isPending) return
    addTodo.mutate(content, { onSuccess: result => { if (result) setInput('') } })
  }

  async function handleClearDone() {
    if (done.length === 0 || clearingDone) return
    setClearingDone(true)
    setClearDoneError(false)
    const results = await Promise.allSettled(done.map(d => deleteTodo.mutateAsync(d.id)))
    const anyFailed = results.some(r => r.status === 'rejected')
    setClearDoneError(anyFailed)
    setClearingDone(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {(completeTodo.isError || addTodo.isError || clearDoneError) && (
        <p style={errorStyle}>
          {completeTodo.isError ? "Couldn't complete todo right now." : addTodo.isError ? "Couldn't add todo right now." : "Couldn't clear completed todos right now."}
        </p>
      )}
      {/* Active todos as cards */}
      {active.length === 0 ? (
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-2)', margin: 0 }}>
          no todos yet
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {active.map(t => (
            <WorkCard
              key={t.id}
              id={String(t.id)}
              title={t.content}
              status={t.status === 'in_progress' ? 'working' : 'scheduled'}
              statusDetail={t.active_form ?? undefined}
              onComplete={() => completeTodo.mutate(t.id)}
            />
          ))}
        </div>
      )}

      {/* Completed count */}
      {done.length > 0 && (
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)', margin: 0 }}>
          {done.length} completed —{' '}
          <button
            onClick={handleClearDone}
            disabled={clearingDone}
            style={{ background: 'none', border: 'none', color: 'var(--c-red)', cursor: clearingDone ? 'not-allowed' : 'pointer', fontSize: 11, padding: 0, opacity: clearingDone ? 0.5 : 1 }}
          >
            {clearingDone ? 'clearing…' : 'clear done'}
          </button>
        </p>
      )}

      {/* Add new */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAdd() }}
          placeholder="add a todo…"
          aria-label="Add a todo"
          style={{
            flex: 1, padding: '6px 12px', borderRadius: 10, border: '1.5px solid var(--line)',
            background: 'var(--surface-2)', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink)',
            outline: 'none',
          }}
        />
        <Button onClick={handleAdd} size="sm" disabled={!input.trim() || addTodo.isPending} icon={<Plus size={12} />}>
          add
        </Button>
      </div>
    </div>
  )
}

const noticeStyle = { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-2)', margin: 0 }
const errorStyle = { ...noticeStyle, color: 'var(--c-red)' }
const retryStyle = { width: 'fit-content', padding: '5px 10px', border: '1px solid var(--line)', borderRadius: 8, background: 'transparent', color: 'var(--ink)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 12 }
