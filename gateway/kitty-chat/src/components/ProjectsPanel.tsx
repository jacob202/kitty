'use client'
import { useState, type CSSProperties } from 'react'
import { useProjects, useProjectNextSteps, useProjectResume, useRefreshProject } from '@/lib/queries'
import type { GatewayNextStep, GatewayProject } from '@/lib/gateway'
import { Button } from '@/components/ui/Button'
import { RefreshCw } from 'lucide-react'

export function ProjectsPanel() {
  const projectsQuery = useProjects()
  const refresh = useRefreshProject()
  const projects = projectsQuery.data ?? []
  const nextSteps = useProjectNextSteps(projects)

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

  return (
    <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
      {projects.length === 0 ? (
        <div style={emptyStateStyle}>
          <strong>No projects yet</strong>
          <span>Projects will appear here when Kitty has durable project context to show.</span>
        </div>
      ) : (
        <section aria-label="Project list" data-testid="project-list" style={projectListStyle}>
          {projects.map((p, index) => (
            <ProjectCard
              key={p.id}
              project={p}
              onRefresh={() => refresh.mutate(p.id)}
              refreshing={refresh.isPending && refresh.variables === p.id}
              isLast={index === projects.length - 1}
              nextStep={nextSteps[index]?.data ?? null}
              nextPending={nextSteps[index]?.isPending ?? false}
              nextError={nextSteps[index]?.isError ?? false}
            />
          ))}
        </section>
      )}
    </div>
  )
}

function ProjectCard({
  project,
  onRefresh,
  refreshing,
  isLast,
  nextStep,
  nextPending,
  nextError,
}: {
  project: GatewayProject
  onRefresh: () => void
  refreshing: boolean
  isLast: boolean
  nextStep: GatewayNextStep | null
  nextPending: boolean
  nextError: boolean
}) {
  const [contextOpen, setContextOpen] = useState(false)
  const touched = project.last_touched
    ? new Date(project.last_touched * 1000).toLocaleDateString('en-CA')
    : null

  return (
    <article
      data-testid="project-row"
      style={{ ...projectRowStyle, borderBottom: isLast ? 'none' : '1px solid var(--color-separator)' }}
    >
      <div style={projectHeaderStyle}>
        <div style={projectIdentityStyle}>
          <div style={projectIdentityLineStyle}>
            <span style={nameStyle}>{project.name}</span>
            <span style={chipStyle}>{project.kind}</span>
            <span style={{ ...chipStyle, color: project.status === 'active' ? 'var(--color-success)' : 'var(--color-text-secondary)' }}>
              {project.status}
            </span>
          </div>
          {touched && <span style={metaStyle}>touched {touched}</span>}
        </div>
        <Button onClick={onRefresh} variant="ghost" size="md" disabled={refreshing} icon={<RefreshCw size={14} />}>
          {refreshing ? 'refreshing…' : 'refresh'}
        </Button>
      </div>

      {project.summary && <p style={summaryStyle}>{project.summary}</p>}

      <div data-testid="project-next-step" style={nextBoxStyle}>
        <div style={nextLabelStyle}>what&apos;s next</div>
        {nextPending ? (
          <p style={mutedStyle}>checking…</p>
        ) : nextError ? (
          <p style={mutedStyle}>couldn&apos;t read the next step — refresh the project to try again.</p>
        ) : nextStep ? (
          <>
            <p style={stepStyle}>{nextStep.step}</p>
            {nextStep.why && <p style={whyStyle}>why: {nextStep.why}</p>}
            {nextStep.recent_win && (
              <p style={{ ...whyStyle, color: 'var(--color-success)' }}>
                recent win: {nextStep.recent_win}
              </p>
            )}
          </>
        ) : (
          <p style={mutedStyle}>no next step generated yet — hit refresh to compose one.</p>
        )}
      </div>

      <button
        type="button"
        aria-expanded={contextOpen}
        aria-label={`Project context for ${project.name}`}
        onClick={() => setContextOpen((open) => !open)}
        style={contextButtonStyle}
      >
        <span>Project context</span>
        <span style={{ color: 'var(--color-text-muted)', fontWeight: 500 }}>
          {contextOpen ? 'Hide' : 'Show'}
        </span>
      </button>

      {contextOpen && (
        <div style={contextPanelStyle}>
          <ProjectContext project={project} />
        </div>
      )}
    </article>
  )
}

function ProjectContext({ project }: { project: GatewayProject }) {
  const resumeQuery = useProjectResume(project.id)

  if (resumeQuery.isLoading) {
    return <p style={mutedStyle}>checking project context…</p>
  }

  if (resumeQuery.isError) {
    return (
      <p style={mutedStyle}>
        project context unavailable (
        {resumeQuery.error instanceof Error ? resumeQuery.error.message : 'gateway error'})
      </p>
    )
  }

  const items = resumeQuery.data?.work?.items ?? []
  const artifacts = resumeQuery.data?.artifacts ?? []
  const conversations = resumeQuery.data?.conversations?.items ?? []
  const conversationError = resumeQuery.data?.conversations?.error ?? null
  const deadlines = resumeQuery.data?.deadlines?.items ?? []
  const deadlineError = resumeQuery.data?.deadlines?.error ?? null
  const actions = project.next_actions.slice(0, 4)

  if (
    actions.length === 0 && items.length === 0 && artifacts.length === 0
    && conversations.length === 0 && deadlines.length === 0
    && !conversationError && !deadlineError
  ) {
    return <p style={mutedStyle}>no related work, conversations, files, or deadlines yet.</p>
  }

  return (
    <>
      {actions.length > 0 && (
        <div>
          <div style={nextLabelStyle}>open actions</div>
          <ul style={{ margin: '6px 0 0 18px', display: 'grid', gap: 4 }}>
            {actions.map((action, index) => (
              <li key={index} style={actionStyle}>{action}</li>
            ))}
          </ul>
        </div>
      )}
      {(conversations.length > 0 || conversationError) && (
        <div>
          <div style={nextLabelStyle}>recent conversations</div>
          {conversationError ? (
            <p style={{ ...mutedStyle, marginTop: 6 }}>{conversationError}</p>
          ) : (
            <ul style={{ margin: '6px 0 0 18px', display: 'grid', gap: 4 }}>
              {conversations.slice(0, 5).map(conversation => (
                <li key={conversation.id} style={actionStyle}>
                  <span>{conversation.title || 'Untitled conversation'}</span>{' '}
                  <span style={metaStyle}>
                    · {new Date(conversation.updated_at * 1000).toLocaleDateString('en-CA')}
                    {conversation.objective ? ` · ${conversation.objective}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {(deadlines.length > 0 || deadlineError) && (
        <div>
          <div style={nextLabelStyle}>deadlines</div>
          {deadlineError ? (
            <p style={{ ...mutedStyle, marginTop: 6 }}>{deadlineError}</p>
          ) : (
            <ul style={{ margin: '6px 0 0 18px', display: 'grid', gap: 4 }}>
              {deadlines.slice(0, 5).map(deadline => (
                <li key={deadline.id} style={actionStyle}>
                  <span>{deadline.obligation}</span>{' '}
                  <span style={metaStyle}>
                    · due {deadline.due_date}{deadline.status === 'needs_jacob' ? ' · needs you' : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {items.length > 0 && (
        <div>
          <div style={nextLabelStyle}>builder work</div>
          <ul style={{ margin: '6px 0 0 18px', display: 'grid', gap: 4 }}>
            {items.slice(0, 5).map(item => (
              <li key={item.id} style={actionStyle}>
                <span>{item.title ?? item.id}</span>{' '}
                <span style={metaStyle}>· {item.state}{item.next_action ? ` · ${item.next_action}` : ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {artifacts.length > 0 && (
        <div>
          <div style={nextLabelStyle}>recent files</div>
          <ul style={{ margin: '6px 0 0 18px', display: 'grid', gap: 4 }}>
            {artifacts.slice(0, 5).map(artifact => (
              <li key={artifact.id} style={actionStyle}>
                <span>{artifact.display_name}</span>{' '}
                <span style={metaStyle}>
                  · {artifact.kind} · {artifact.state} · {new Date(artifact.created_at * 1000).toLocaleDateString('en-CA')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}

const projectHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: 12,
}

const projectIdentityStyle: CSSProperties = {
  display: 'grid',
  gap: 6,
  minWidth: 0,
  flex: 1,
}

const projectIdentityLineStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  flexWrap: 'wrap',
}

const projectListStyle: CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  overflow: 'hidden',
}

const projectRowStyle: CSSProperties = {
  padding: '20px 22px',
  display: 'grid',
  gap: 14,
}

const emptyStateStyle: CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  padding: 24,
  display: 'grid',
  gap: 6,
  fontSize: 14,
  color: 'var(--color-text-secondary)',
}

const nameStyle: CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 700,
  fontSize: 18,
  color: 'var(--color-text-primary)',
}

const chipStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 11.5,
  fontWeight: 600,
  padding: '3px 8px',
  border: '1px solid var(--color-separator)',
  borderRadius: 999,
  color: 'var(--color-text-secondary)',
}

const metaStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 11.5,
  color: 'var(--color-text-muted)',
}

const summaryStyle: CSSProperties = {
  fontSize: 14,
  lineHeight: 1.55,
  color: 'var(--color-text-secondary)',
}

const nextBoxStyle: CSSProperties = {
  background: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)',
  padding: '12px 14px',
  display: 'grid',
  gap: 5,
}

const nextLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  fontWeight: 700,
  color: 'var(--color-text-secondary)',
}

const stepStyle: CSSProperties = {
  fontSize: 15,
  fontWeight: 600,
  lineHeight: 1.5,
  color: 'var(--color-text-primary)',
}

const whyStyle: CSSProperties = {
  fontSize: 13,
  color: 'var(--color-text-secondary)',
  lineHeight: 1.5,
}

const actionStyle: CSSProperties = {
  fontSize: 13,
  color: 'var(--color-text-primary)',
  lineHeight: 1.5,
}

const contextButtonStyle: CSSProperties = {
  minHeight: 44,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '8px 10px',
  margin: '0 -10px -4px',
  borderRadius: 'var(--r-control)',
  color: 'var(--color-text-secondary)',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
  background: 'transparent',
}

const contextPanelStyle: CSSProperties = {
  display: 'grid',
  gap: 14,
  padding: '14px 0 2px',
  borderTop: '1px solid var(--color-separator)',
}

const mutedStyle: CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--color-text-secondary)',
  lineHeight: 1.5,
}

const errorBoxStyle: CSSProperties = {
  border: '1px solid var(--color-destructive)',
  background: 'var(--color-surface)',
  borderRadius: 'var(--r-control)',
  padding: 16,
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--color-destructive)',
  lineHeight: 1.6,
}
