'use client'
import type { CSSProperties } from 'react'
import { useProjects, useProjectNext, useRefreshProject, useCreateProject } from '@/lib/queries'
import type { GatewayProject } from '@/lib/gateway'
import { Card } from '@/components/ui/Card'
import { SectionLabel } from '@/components/ui/SectionLabel'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'

export function ProjectsPanel() {
  const projectsQuery = useProjects()
  const refresh = useRefreshProject()
  const createProject = useCreateProject()

  const [newName, setNewName] = useState('')
  const [newKind, setNewKind] = useState('')

  if (projectsQuery.isLoading) {
    return <p style={mutedStyle}>loading projects…</p>
  }

  if (projectsQuery.isError) {
    return (
      <div style={errorBoxStyle}>
        <strong>projects unavailable</strong> —{' '}
        {projectsQuery.error instanceof Error ? projectsQuery.error.message : 'gateway error'}.
        GET /projects didn&apos;t answer; is the gateway up?
      </div>
    )
  }

  const projects = projectsQuery.data ?? []

  function handleCreate() {
    if (!newName.trim() || !newKind.trim()) return
    createProject.mutate({ name: newName.trim(), kind: newKind.trim() })
    setNewName('')
    setNewKind('')
  }

  return (
    <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
      <header>
        <h2 style={titleStyle}>projects</h2>
        <p style={subtitleStyle}>
          every project carries a generated next step — the thing to reach for, not a repo task.
        </p>
      </header>

      <Card style={{ display: 'grid', gap: 12 }}>
        <SectionLabel>create project</SectionLabel>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="project name"
            style={inputStyle}
          />
          <input
            value={newKind}
            onChange={e => setNewKind(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            placeholder="kind (e.g. app, plugin)"
            style={inputStyle}
          />
          <Button
            variant="primary"
            onClick={handleCreate}
            disabled={!newName.trim() || !newKind.trim() || createProject.isPending}
          >
            {createProject.isPending ? 'creating…' : 'add'}
          </Button>
        </div>
      </Card>

      {projects.length === 0 && (
        <p style={mutedStyle}>
          no projects registered yet — add one above.
        </p>
      )}

      {projects.map(p => (
        <ProjectCard
          key={p.id}
          project={p}
          onRefresh={() => refresh.mutate(p.id)}
          refreshing={refresh.isPending && refresh.variables === p.id}
        />
      ))}
    </div>
  )
}

function ProjectCard({
  project,
  onRefresh,
  refreshing,
}: {
  project: GatewayProject
  onRefresh: () => void
  refreshing: boolean
}) {
  const nextQuery = useProjectNext(project.id)
  const touched = project.last_touched
    ? new Date(project.last_touched * 1000).toLocaleDateString('en-CA')
    : null

  return (
    <Card style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={nameStyle}>{project.name}</span>
        <span style={chipStyle}>{project.kind}</span>
        <span style={{ ...chipStyle, color: project.status === 'active' ? 'var(--c-green)' : 'var(--ink-2)' }}>
          {project.status}
        </span>
        {touched && <span style={metaStyle}>touched {touched}</span>}
        <span style={{ flex: 1 }} />
        <Button onClick={onRefresh} disabled={refreshing} variant="action">
          {refreshing ? 'refreshing…' : '↻ refresh'}
        </Button>
      </div>

      {project.summary && <p style={summaryStyle}>{project.summary}</p>}

      <div style={nextBoxStyle}>
        <SectionLabel style={{ color: 'var(--cat-ginger)' }}>what&apos;s next</SectionLabel>
        {nextQuery.isLoading ? (
          <p style={mutedStyle}>checking…</p>
        ) : nextQuery.isError ? (
          <p style={mutedStyle}>
            couldn&apos;t read the next step (
            {nextQuery.error instanceof Error ? nextQuery.error.message : 'gateway error'})
          </p>
        ) : nextQuery.data ? (
          <>
            <p style={stepStyle}>{nextQuery.data.step}</p>
            {nextQuery.data.why && <p style={whyStyle}>why: {nextQuery.data.why}</p>}
            {nextQuery.data.recent_win && (
              <p style={{ ...whyStyle, color: 'var(--c-green)' }}>
                recent win: {nextQuery.data.recent_win}
              </p>
            )}
          </>
        ) : (
          <p style={mutedStyle}>no next step generated yet — hit refresh to compose one.</p>
        )}
      </div>

      {project.next_actions.length > 0 && (
        <div>
          <SectionLabel>open actions</SectionLabel>
          <ul style={{ margin: '4px 0 0 16px', display: 'grid', gap: 2 }}>
            {project.next_actions.slice(0, 4).map((a, i) => (
              <li key={i} style={actionStyle}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 800,
  fontSize: 28,
  letterSpacing: 0,
  color: 'var(--ink)',
}

const subtitleStyle: CSSProperties = {
  fontSize: 13,
  color: 'var(--ink-2)',
  marginTop: 2,
}



const nameStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 700,
  fontSize: 18,
  color: 'var(--ink)',
}

const chipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.06em',
  textTransform: 'lowercase',
  padding: '2px 8px',
  border: '1px solid var(--line)',
  borderRadius: 999,
  color: 'var(--ink-2)',
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const summaryStyle: CSSProperties = {
  fontSize: 14,
  lineHeight: 1.55,
  color: 'var(--ink)',
}

const nextBoxStyle: CSSProperties = {
  background: 'var(--ginger-fade)',
  border: '1.5px solid var(--cat-ginger)',
  borderRadius: 10,
  padding: '10px 14px',
  display: 'grid',
  gap: 4,
}



const stepStyle: CSSProperties = {
  fontSize: 15,
  fontWeight: 600,
  lineHeight: 1.5,
  color: 'var(--ink)',
}

const whyStyle: CSSProperties = {
  fontSize: 12,
  color: 'var(--ink-2)',
  lineHeight: 1.5,
}

const actionStyle: CSSProperties = {
  fontSize: 13,
  color: 'var(--ink)',
  lineHeight: 1.5,
}



const mutedStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--ink-2)',
}

const errorBoxStyle: CSSProperties = {
  border: '1.5px solid var(--c-red)',
  background: 'var(--surface)',
  borderRadius: 12,
  padding: 16,
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--c-red)',
  lineHeight: 1.6,
}

const inputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--bg)',
  border: '1.5px solid var(--line)',
  borderRadius: 10,
  padding: '8px 12px',
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  color: 'var(--ink)',
  outline: 'none',
}
