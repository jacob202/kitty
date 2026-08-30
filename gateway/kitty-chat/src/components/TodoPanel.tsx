'use client'
import { useState } from 'react'
import { useTodos, useAddTodo, useCompleteTodo, useDeleteTodo } from '@/lib/queries'
import { Button } from '@/components/ui/Button'
import { WorkCard } from '@/components/shared/WorkCard'
import { Check, X, Plus } from 'lucide-react'

export function TodoPanel() {
  const todosQuery = useTodos()
  const addTodo = useAddTodo()
  const completeTodo = useCompleteTodo()
  const deleteTodo = useDeleteTodo()
  const [input, setInput] = useState('')

  const todos = todosQuery.data ?? []
  const active = todos.filter(t => t.status === 'pending' || t.status === 'in_progress')
  const done = todos.filter(t => t.status === 'completed')

  function handleAdd() {
    const content = input.trim()
    if (!content || addTodo.isPending) return
    addTodo.mutate(content, { onSuccess: result => { if (result) setInput('') } })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
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
              onRetry={() => completeTodo.mutate(t.id)}
            />
          ))}
        </div>
      )}

      {/* Completed count */}
      {done.length > 0 && (
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)', margin: 0 }}>
          {done.length} completed —{' '}
          <button
            onClick={() => done.forEach(d => deleteTodo.mutate(d.id))}
            style={{ background: 'none', border: 'none', color: 'var(--c-red)', cursor: 'pointer', fontSize: 11, padding: 0 }}
          >
            clear done
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
