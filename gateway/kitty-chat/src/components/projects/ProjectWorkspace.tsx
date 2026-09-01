import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { ArrowRight, BriefcaseBusiness, MessageSquare, RefreshCw, X } from 'lucide-react'

import { ArtifactCanvas, canPreviewArtifact } from '@/components/artifacts/ArtifactCanvas'
import { Button } from '@/components/ui/Button'
import { describeFailure } from '@/lib/failure-copy'
import { useDialogFocus } from '@/hooks/useDialogFocus'
import { projectNextStepCopy, projectSummaryCopy } from '@/lib/project-copy'
import type { GatewayArtifact, GatewayNextStep, GatewayProject, GatewayProjectArtifact } from '@/lib/gateway'
import { useProjectResume, useSetActiveProject } from '@/lib/queries'

export function ProjectWorkspace({
  project,
  nextStep,
  onClose,
  onNavigate,
  onStartChat = () => {},
  onRefresh,
  refreshing = false,
  refreshError = null,
  isMobile = false,
}: {
  project: GatewayProject
  nextStep: GatewayNextStep | null
  onClose: () => void
  onNavigate: (view: string) => void
  onStartChat?: () => void
  onRefresh?: () => void
  refreshing?: boolean
  refreshError?: string | null
  isMobile?: boolean
}) {
  const resume = useProjectResume(project.id)
  const setActiveProject = useSetActiveProject()
  const [selectedArtifact, setSelectedArtifact] = useState<GatewayArtifact | null>(null)
  const [activationError, setActivationError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const closeWorkspace = () => {
    mountedRef.current = false
    onClose()
  }
  const dialogRef = useDialogFocus<HTMLElement>({ open: true, enabled: !selectedArtifact, onClose: closeWorkspace })

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const summary = projectSummaryCopy(project) || 'No project summary yet.'
  const nextCopy = nextStep ? projectNextStepCopy(project, nextStep) : null

  const artifacts = useMemo(
    () => (resume.data?.artifacts ?? []).map(item => toArtifact(project.id, item)),
    [project.id, resume.data?.artifacts],
  )

  const activateAndNavigate = async (view: string) => {
    setActivationError(null)
    try {
      await setActiveProject.mutateAsync(project.id)
      if (!mountedRef.current) return
      if (view === 'chat') onStartChat()
      onNavigate(view)
    } catch (err) {
      if (mountedRef.current) setActivationError(describeFailure(err))
    }
  }

  return (
    <div style={backdropStyle} onMouseDown={(event) => { if (event.currentTarget === event.target) closeWorkspace() }}>
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${project.name} project workspace`}
        aria-hidden={selectedArtifact ? true : undefined}
        inert={selectedArtifact ? true : undefined}
        style={panelStyle}
      >
        <header style={headerStyle}>
          <div style={{ minWidth: 0 }}>
            <div style={eyebrowStyle}>project workspace</div>
            <h2 style={titleStyle}>{project.name}</h2>
            <p style={summaryStyle}>{summary}</p>
          </div>
          <button type="button" aria-label="Close project workspace" onClick={closeWorkspace} style={iconButtonStyle}><X size={18} /></button>
        </header>

        <div style={toolbarStyle}>
          <Button onClick={() => void activateAndNavigate('chat')} loading={setActiveProject.isPending} icon={<MessageSquare size={14} />}>
            Continue in chat
          </Button>
          <Button onClick={() => void activateAndNavigate('work')} variant="secondary" disabled={setActiveProject.isPending} icon={<BriefcaseBusiness size={14} />}>
            Open work
          </Button>
          {onRefresh && (
            <Button onClick={onRefresh} variant="ghost" disabled={refreshing} icon={<RefreshCw size={14} />}>
              {refreshing ? 'refreshing…' : 'Refresh'}
            </Button>
          )}
        </div>
        {activationError && <p role="alert" style={errorBannerStyle}>{activationError}</p>}
        {refreshError && <p role="alert" style={errorBannerStyle}>{refreshError}</p>}

        <div style={bodyStyle}>
          <section style={heroSectionStyle}>
            <div style={sectionLabelStyle}>what&apos;s next</div>
            {nextCopy ? (
              <>
                <div style={nextStepStyle}>{nextCopy.step}</div>
                {nextCopy.why && <div style={detailStyle}>{nextCopy.why}</div>}
                {nextCopy.recent_win && <div style={winStyle}>Recent win · {nextCopy.recent_win}</div>}
              </>
            ) : (
              <div style={mutedStyle}>No generated next step yet.</div>
            )}
          </section>

          {resume.isLoading && <p style={mutedStyle}>Loading project context…</p>}
          {resume.isError && <p role="status" style={mutedStyle}>Project context unavailable — {describeFailure(resume.error)}</p>}

          {project.next_actions.length > 0 && (
            <WorkspaceSection title="Open actions">
              {project.next_actions.slice(0, 5).map((action, index) => <WorkspaceRow key={`${action}-${index}`} title={action} />)}
            </WorkspaceSection>
          )}

          {(resume.data?.conversations?.items?.length ?? 0) > 0 && (
            <WorkspaceSection title="Recent conversations">
              {resume.data!.conversations.items.slice(0, 5).map(conversation => (
                <WorkspaceRow key={conversation.id} title={conversation.title || 'Untitled conversation'} detail={conversation.objective || undefined} />
              ))}
            </WorkspaceSection>
          )}
          {resume.data?.conversations?.error && <SourceWarning label="Conversations" message={resume.data.conversations.error} />}

          {(resume.data?.deadlines?.items?.length ?? 0) > 0 && (
            <WorkspaceSection title="Deadlines">
              {resume.data!.deadlines.items.slice(0, 5).map(deadline => (
                <WorkspaceRow key={deadline.id} title={deadline.obligation} detail={`Due ${deadline.due_date}${deadline.status === 'needs_jacob' ? ' · needs you' : ''}`} />
              ))}
            </WorkspaceSection>
          )}
          {resume.data?.deadlines?.error && <SourceWarning label="Deadlines" message={resume.data.deadlines.error} />}

          {(resume.data?.work?.items?.length ?? 0) > 0 && (
            <WorkspaceSection title="Builder work">
              {resume.data!.work.items.slice(0, 5).map(item => (
                <WorkspaceRow key={item.id} title={item.title || item.id} detail={`${item.state}${item.next_action ? ` · ${item.next_action}` : ''}`} />
              ))}
            </WorkspaceSection>
          )}

          {artifacts.length > 0 && (
            <WorkspaceSection title="Artifacts">
              {artifacts.slice(0, 6).map(artifact => (
                <div key={artifact.id} style={artifactRowStyle}>
                  <div style={{ minWidth: 0 }}>
                    <div style={rowTitleStyle}>{artifact.display_name}</div>
                    <div style={rowDetailStyle}>{artifact.kind} · {artifact.state}</div>
                  </div>
                  {canPreviewArtifact(artifact) && (
                    <button type="button" aria-label={`Open ${artifact.display_name}`} onClick={() => setSelectedArtifact(artifact)} style={smallButtonStyle}>
                      Open <ArrowRight size={12} />
                    </button>
                  )}
                </div>
              ))}
            </WorkspaceSection>
          )}
        </div>
      </section>

      {selectedArtifact && (
        <ArtifactCanvas artifact={selectedArtifact} isMobile={isMobile} onClose={() => setSelectedArtifact(null)} />
      )}
    </div>
  )
}

function toArtifact(projectId: number, artifact: GatewayProjectArtifact): GatewayArtifact {
  return {
    ...artifact,
    project_id: projectId,
    created_by: 'project',
    metadata: {},
  }
}

function WorkspaceSection({ title, children }: { title: string; children: ReactNode }) {
  return <section style={sectionStyle}><div style={sectionLabelStyle}>{title}</div><div style={rowsStyle}>{children}</div></section>
}

function WorkspaceRow({ title, detail }: { title: string; detail?: string }) {
  return <div style={rowStyle}><div style={rowTitleStyle}>{title}</div>{detail && <div style={rowDetailStyle}>{detail}</div>}</div>
}

function SourceWarning({ label, message }: { label: string; message: string }) {
  return <div role="status" style={warningStyle}><strong>{label} unavailable.</strong> {message}</div>
}

const backdropStyle: CSSProperties = { position: 'fixed', inset: 0, zIndex: 950, background: 'rgba(0,0,0,0.42)', display: 'flex', justifyContent: 'flex-end' }
const panelStyle: CSSProperties = { width: 'min(760px, 100vw)', height: '100%', background: 'var(--color-background, var(--bg))', borderLeft: '1px solid var(--color-separator, var(--line))', boxShadow: '-20px 0 50px rgba(0,0,0,0.22)', display: 'flex', flexDirection: 'column', minWidth: 0 }
const headerStyle: CSSProperties = { padding: '18px 20px 14px', display: 'flex', justifyContent: 'space-between', gap: 16, borderBottom: '1px solid var(--color-separator, var(--line))' }
const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--color-text-secondary, var(--ink-2))' }
const titleStyle: CSSProperties = { margin: '3px 0 0', fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--color-text-primary, var(--ink))' }
const summaryStyle: CSSProperties = { margin: '6px 0 0', maxWidth: 620, fontSize: 13, lineHeight: 1.5, color: 'var(--color-text-secondary, var(--ink-2))' }
const iconButtonStyle: CSSProperties = { width: 44, height: 44, border: '1px solid var(--color-separator, var(--line))', borderRadius: 'var(--r-control, 8px)', background: 'var(--color-surface, var(--surface))', color: 'var(--color-text-primary, var(--ink))', display: 'grid', placeItems: 'center', cursor: 'pointer', flexShrink: 0 }
const toolbarStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 8, padding: '12px 20px', borderBottom: '1px solid var(--color-separator, var(--line))' }
const errorBannerStyle: CSSProperties = { margin: 0, padding: '8px 20px', color: 'var(--color-destructive)', fontSize: 12, borderBottom: '1px solid var(--color-separator, var(--line))' }
const bodyStyle: CSSProperties = { flex: 1, minHeight: 0, overflowY: 'auto', padding: 20, display: 'grid', alignContent: 'start', gap: 18 }
const heroSectionStyle: CSSProperties = { padding: 16, borderRadius: 'var(--r-surface, 12px)', border: '1px solid var(--color-separator, var(--line))', background: 'var(--color-surface-elevated, var(--surface))', display: 'grid', gap: 6 }
const sectionStyle: CSSProperties = { display: 'grid', gap: 8 }
const sectionLabelStyle: CSSProperties = { fontFamily: 'var(--font-body)', fontWeight: 750, fontSize: 12, color: 'var(--color-text-secondary, var(--ink-2))', textTransform: 'uppercase', letterSpacing: '0.05em' }
const nextStepStyle: CSSProperties = { fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary, var(--ink))', lineHeight: 1.35 }
const detailStyle: CSSProperties = { fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-secondary, var(--ink-2))' }
const winStyle: CSSProperties = { ...detailStyle, color: 'var(--color-success)' }
const mutedStyle: CSSProperties = { margin: 0, fontSize: 12, color: 'var(--color-text-secondary, var(--ink-2))' }
const rowsStyle: CSSProperties = { display: 'grid', gap: 7 }
const rowStyle: CSSProperties = { padding: '10px 12px', border: '1px solid var(--color-separator, var(--line))', borderRadius: 8, background: 'var(--color-surface, var(--surface))' }
const artifactRowStyle: CSSProperties = { ...rowStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }
const rowTitleStyle: CSSProperties = { fontSize: 13, fontWeight: 650, color: 'var(--color-text-primary, var(--ink))', overflowWrap: 'anywhere' }
const rowDetailStyle: CSSProperties = { marginTop: 2, fontSize: 11, color: 'var(--color-text-secondary, var(--ink-2))', overflowWrap: 'anywhere' }
const smallButtonStyle: CSSProperties = { minHeight: 38, border: '1px solid var(--color-separator, var(--line))', borderRadius: 8, background: 'transparent', color: 'var(--color-accent, var(--primary))', padding: '6px 9px', display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 700, cursor: 'pointer', flexShrink: 0 }
const warningStyle: CSSProperties = { padding: '9px 11px', border: '1px solid var(--color-warning)', borderRadius: 8, fontSize: 11, lineHeight: 1.4, color: 'var(--color-text-secondary, var(--ink-2))' }
