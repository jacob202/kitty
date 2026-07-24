'use client'
import { TaskPanel } from '@/components/TaskPanel'
import { TodoPanel } from '@/components/TodoPanel'

export default function WorkView({ isMobile }: { isMobile: boolean }) {
  return (
    <div style={{
      flex: 1,
      padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
      display: 'grid', gap: 24, alignContent: 'start',
    }}>
      <TaskPanel />
      <TodoPanel />
    </div>
  )
}
