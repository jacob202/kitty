'use client'
import { useTodos } from '@/lib/queries'
import { useGatewayRuntimeManifest } from '@/lib/queries'
import { TaskPanel } from '@/components/TaskPanel'
import { TodoPanel } from '@/components/TodoPanel'
import { BuilderPanel } from '@/components/BuilderSurface'
import { ArrowRight } from 'lucide-react'

export default function WorkView({ isMobile, onNavigate }: { isMobile: boolean; onNavigate?: (view: string) => void }) {
  const todosQuery = useTodos()
  const manifestQuery = useGatewayRuntimeManifest()
  const builderFact = manifestQuery.data?.execution.builder
  const builderSnapshot = builderFact?.value
  const activeTodos = (todosQuery.data ?? []).filter(
    t => t.status === 'pending' || t.status === 'in_progress'
  )
  const builderAttention = builderSnapshot
    ? builderSnapshot.initiatives.flatMap(i => i.packets).filter(p =>
        p.task_state === 'blocked' || p.task_state === 'failed' || p.budget?.exhausted === true || p.failure_kind !== null
      ).length
    : 0

  const hasAttention = activeTodos.length > 0 || builderAttention > 0

  return (
    <div style={{
      flex: 1,
      padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
      display: 'grid', gap: 24, alignContent: 'start',
    }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Work</h1>
        <p style={{ margin: '4px 0 0', color: 'var(--ink-2)' }}>
          Life tasks, project work, and KittyBuilder execution in one place.
        </p>
      </header>

      {hasAttention && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))',
          gap: 12,
        }}>
          {activeTodos.length > 0 && (
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: '14px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: 'var(--c-yellow)', flexShrink: 0,
              }} />
              <span style={{
                fontFamily: 'var(--font-body)',
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--ink)',
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {activeTodos[0].content}
              </span>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--ink-2)',
                flexShrink: 0,
              }}>
                {activeTodos.length === 1 ? '1 todo' : `${activeTodos.length} todos`}
              </span>
            </div>
          )}
          {builderAttention > 0 && (
            <button
              type="button"
              onClick={() => onNavigate?.('builder')}
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--line)',
                borderRadius: 12,
                padding: '14px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                cursor: 'pointer',
                textAlign: 'left',
                color: 'var(--ink)',
              }}
            >
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: builderAttention > 0 ? 'var(--c-red)' : 'var(--c-green)',
                flexShrink: 0,
              }} />
              <span style={{
                fontFamily: 'var(--font-body)',
                fontSize: 14,
                fontWeight: 600,
                flex: 1,
              }}>
                {builderAttention} builder {builderAttention === 1 ? 'packet' : 'packets'} need{ builderAttention === 1 ? 's' : ''} attention
              </span>
              <ArrowRight size={14} style={{ color: 'var(--ink-2)', flexShrink: 0 }} />
            </button>
          )}
        </div>
      )}

      <TaskPanel />
      <TodoPanel />
      <BuilderPanel />
    </div>
  )
}
