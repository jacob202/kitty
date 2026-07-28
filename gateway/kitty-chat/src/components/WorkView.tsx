'use client'
import { TaskPanel } from '@/components/TaskPanel'
import { TodoPanel } from '@/components/TodoPanel'
import { BuilderPanel } from '@/components/BuilderSurface'

export default function WorkView({ isMobile }: { isMobile: boolean }) {
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
<TaskPanel />
<TodoPanel />
<BuilderPanel />
</div>
)
}
