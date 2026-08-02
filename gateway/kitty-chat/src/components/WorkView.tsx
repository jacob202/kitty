'use client'
import { useTodos } from '@/lib/queries'
import { useGatewayRuntimeManifest } from '@/lib/queries'
import { useMaybeKitty } from '@/state/KittyContext'
import { TaskPanel } from '@/components/TaskPanel'
import { TodoPanel } from '@/components/TodoPanel'
import { BuilderPanel, attentionCount, activePacketCount } from '@/components/BuilderSurface'
import { ArrowRight, Wrench } from 'lucide-react'
import type { BuilderStatusSnapshot } from '@/lib/gateway'

export default function WorkView({ isMobile, onNavigate }: { isMobile: boolean; onNavigate?: (view: string) => void }) {
  const todosQuery = useTodos()
  const manifestQuery = useGatewayRuntimeManifest()
  const builderFact = manifestQuery.data?.execution.builder
  const builderSnapshot = builderFact?.value
  const activeTodos = (todosQuery.data ?? []).filter(
    t => t.status === 'pending' || t.status === 'in_progress'
  )
  const builderAttention = builderSnapshot
    ? attentionCount(builderSnapshot)
    : 0

  const k = useMaybeKitty()
  const showBuilder = k?.showBuilderMachinery ?? false
  const hasAttention = activeTodos.length > 0 || (showBuilder && builderAttention > 0)

  return (
    <div style={{
      flex: 1,
      padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
      display: 'grid', gap: 24, alignContent: 'start',
    }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--ink)' }}>Work</h1>
        <p style={{ margin: '4px 0 0', color: 'var(--ink-2)' }}>
          Life tasks, project work{showBuilder ? ', and KittyBuilder execution' : ''} in one place.
        </p>
      </header>

      {builderAttention > 0 && !showBuilder && (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--line)',
          borderRadius: 12, padding: '14px 16px',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <Wrench size={15} style={{ color: 'var(--ink-2)', flexShrink: 0 }} />
          <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--ink-2)', flex: 1 }}>
            {builderAttention} builder {builderAttention === 1 ? 'packet needs' : 'packets need'} attention
          </span>
          <button type="button" onClick={() => k?.setShowBuilderMachinery(true)}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 4, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink-2)', cursor: 'pointer' }}>
            show
          </button>
        </div>
      )}

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
          {showBuilder && builderAttention > 0 && (
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
                background: 'var(--c-red)',
                flexShrink: 0,
              }} />
              <span style={{
                fontFamily: 'var(--font-body)',
                fontSize: 14,
                fontWeight: 600,
                flex: 1,
              }}>
                {builderAttention} builder {builderAttention === 1 ? 'packet' : 'packets'} need attention
                <BuilderBreakdown snapshot={builderSnapshot} />
              </span>
              <ArrowRight size={14} style={{ color: 'var(--ink-2)', flexShrink: 0 }} />
            </button>
          )}
        </div>
      )}

      <TaskPanel />
      <TodoPanel />
      {showBuilder && (
      <section>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--ink)' }}>
            Builder
          </h2>
          <button
            type="button"
            onClick={() => onNavigate?.('builder')}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              fontWeight: 600,
              padding: '4px 12px',
              borderRadius: 4,
              border: '1px solid var(--line)',
              background: 'var(--surface)',
              color: 'var(--ink-2)',
              cursor: 'pointer',
            }}
          >
            Open full Builder
          </button>
        </div>
        <BuilderPanel />
      </section>
      )}
    </div>
  )
}

function BuilderBreakdown({ snapshot }: { snapshot?: BuilderStatusSnapshot | null }) {
  if (!snapshot) return null
  const seen = new Set<string>()
  const packets = snapshot.initiatives.flatMap(i => i.packets)
    .filter(p => { if (seen.has(p.packet_id)) return false; seen.add(p.packet_id); return true })
  const blocked = packets.filter(p => p.task_state === 'blocked').length
  const failed = packets.filter(p => p.task_state === 'failed' || p.failure_kind !== null).length
  const budget = packets.filter(p => p.budget.exhausted === true).length
  const parts: string[] = []
  if (blocked > 0) parts.push(`${blocked} blocked`)
  if (failed > 0) parts.push(`${failed} failed`)
  if (budget > 0) parts.push(`${budget} out of budget`)
  if (parts.length === 0) return null
  return (
    <span style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', marginTop: 2, lineHeight: 1.5 }}>
      {parts.join(' · ')}
    </span>
  )
}
