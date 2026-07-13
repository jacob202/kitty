'use client'
import { useActiveProject, useProjectNext, useDeadlines } from '@/lib/queries'
import { Chat } from '@/lib/types'

interface Props {
  activeChat: Chat | null
}

function formatDate(raw: string | null | undefined): string {
  if (!raw) return ''
  try {
    const d = new Date(raw)
    const now = new Date()
    const diffDays = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
    if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`
    if (diffDays === 0) return 'today'
    if (diffDays === 1) return 'tomorrow'
    return `${diffDays}d`
  } catch {
    return raw
  }
}

export function GoalSidebar({ activeChat }: Props) {
  const activeProjectQuery = useActiveProject()
  const project = activeProjectQuery.data?.project ?? null
  const nextQuery = useProjectNext(project?.id ?? 0)
  const deadlinesQuery = useDeadlines('open')

  const nextStep = nextQuery.data?.step
  const nearestDeadline = deadlinesQuery.data?.deadlines?.[0]
  const objective = activeChat?.objective

  if (!project && !objective && !nearestDeadline) return null

  return (
    <div style={{
      padding: '12px 14px',
      borderBottom: '1.5px solid var(--line)',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      background: 'var(--surface-2)',
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--ink-2)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--c-yellow)' }} />
        thread focus
      </div>

      {objective && (
        <div style={{
          padding: '8px 10px',
          borderRadius: 8,
          background: 'var(--surface)',
          border: '1.5px solid var(--line)',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--ink-2)',
            marginBottom: 3,
          }}>goal</div>
          <div style={{ fontSize: 12, lineHeight: 1.45, color: 'var(--ink)' }}>{objective}</div>
        </div>
      )}

      {project && (
        <div style={{
          padding: '8px 10px',
          borderRadius: 8,
          background: 'var(--surface)',
          border: '1.5px solid var(--line)',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--ink-2)',
            marginBottom: 3,
          }}>project</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>{project.name}</div>
          {nextStep && (
            <div style={{
              marginTop: 6,
              paddingTop: 6,
              borderTop: '1px solid var(--line)',
              fontSize: 11,
              lineHeight: 1.45,
              color: 'var(--ink-2)',
            }}>
              next: {nextStep}
            </div>
          )}
        </div>
      )}

      {nearestDeadline && (
        <div style={{
          padding: '8px 10px',
          borderRadius: 8,
          background: 'var(--surface)',
          border: '1.5px solid var(--line)',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--ink-2)',
            }}>nearest deadline</span>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--c-red)',
              fontWeight: 600,
            }}>{formatDate(nearestDeadline.due_date)}</span>
          </div>
          <div style={{ marginTop: 3, fontSize: 11, lineHeight: 1.45, color: 'var(--ink)' }}>
            {nearestDeadline.obligation}
          </div>
        </div>
      )}
    </div>
  )
}
