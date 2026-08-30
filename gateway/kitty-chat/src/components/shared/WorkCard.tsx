'use client'
import { type ReactNode } from 'react'
import { MessageCircle, ArrowRight, RotateCcw, Play, X } from 'lucide-react'

export type WorkStatus = 'working' | 'needs_user' | 'scheduled' | 'paused' | 'failed' | 'completed' | 'unavailable' | 'degraded' | 'canceled'

export interface WorkArtifact {
  type: 'image' | 'document' | 'note' | 'report' | 'quiz' | 'code'
  title: string
  preview?: string
}

export interface WorkCardProps {
  id: string
  title: string
  sourceTitle?: string
  sourceChatId?: string
  status: WorkStatus
  statusDetail?: string
  progress?: number
  artifacts?: WorkArtifact[]
  onRetry?: () => void
  onResume?: () => void
  onCancel?: () => void
  onNavigate?: () => void
}

const STATUS_CONFIG: Record<WorkStatus, { label: string; color: string; bg: string }> = {
  working:    { label: 'working',      color: 'var(--c-yellow)', bg: 'rgba(232, 196, 106, 0.12)' },
  needs_user: { label: 'needs you',    color: 'var(--c-yellow)', bg: 'rgba(232, 196, 106, 0.15)' },
  scheduled:  { label: 'scheduled',    color: 'var(--c-blue)',   bg: 'rgba(111, 160, 217, 0.10)' },
  paused:     { label: 'paused',       color: 'var(--ink-2)',    bg: 'rgba(154, 160, 180, 0.10)' },
  failed:     { label: 'failed',       color: 'var(--c-red)',    bg: 'rgba(217, 122, 102, 0.12)' },
  completed:  { label: 'done',         color: 'var(--c-green)',  bg: 'rgba(127, 176, 105, 0.10)' },
  unavailable:{ label: 'offline',      color: 'var(--c-red)',    bg: 'rgba(217, 122, 102, 0.08)' },
  degraded:   { label: 'limited',      color: 'var(--c-yellow)', bg: 'rgba(232, 196, 106, 0.08)' },
  canceled:   { label: 'canceled',     color: 'var(--ink-2)',    bg: 'rgba(154, 160, 180, 0.08)' },
}

const artifactTypeLabels: Record<string, string> = {
  image: 'IMG', document: 'DOC', note: 'NOTE', report: 'RPT', quiz: 'QUIZ', code: 'CODE',
}

export function WorkCard({
  title,
  sourceTitle,
  sourceChatId,
  status,
  statusDetail,
  progress,
  artifacts,
  onRetry,
  onResume,
  onCancel,
  onNavigate,
}: WorkCardProps) {
  const cfg = STATUS_CONFIG[status]
  const showProgress = progress !== undefined && (status === 'working' || status === 'needs_user')

  return (
    <div
      role="status"
      aria-label={`${title}: ${cfg.label}`}
      style={{
        border: `1px solid ${status === 'working' ? 'var(--c-yellow)' : status === 'needs_user' ? 'var(--c-yellow)' : status === 'failed' ? 'var(--c-red)' : 'var(--line)'}`,
        borderRadius: 12,
        background: 'var(--surface)',
        overflow: 'hidden',
        transition: 'border-color 0.2s ease',
      }}
    >
      <div style={{ padding: '12px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--ink)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {title}
              </span>
              <StatusPill status={status} />
            </div>
            {sourceChatId && sourceTitle && (
              <button
                onClick={onNavigate}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  border: 'none',
                  background: 'transparent',
                  cursor: onNavigate ? 'pointer' : 'default',
                  color: 'var(--ink-2)',
                  fontSize: 12,
                  fontFamily: 'var(--font-body)',
                  padding: 0,
                }}
              >
                <MessageCircle size={11} />
                {sourceTitle}
                {onNavigate && <ArrowRight size={11} />}
              </button>
            )}
          </div>
          {showProgress && (
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--c-yellow)',
              flexShrink: 0,
            }}>
              {progress}%
            </span>
          )}
        </div>

        {statusDetail && (
          <div style={{
            fontSize: 13,
            color: 'var(--ink-2)',
            marginTop: 6,
            lineHeight: 1.45,
          }}>
            {statusDetail}
          </div>
        )}

        {showProgress && (
          <div style={{
            height: 3,
            borderRadius: 99,
            background: 'var(--surface-2)',
            marginTop: 8,
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${Math.min(100, Math.max(0, progress ?? 0))}%`,
              background: 'var(--c-yellow)',
              borderRadius: 99,
              transition: 'width 0.3s ease',
            }} />
          </div>
        )}

        {artifacts && artifacts.length > 0 && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            marginTop: 10,
          }}>
            {artifacts.slice(0, 4).map((a, i) => (
              <span key={i} style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '3px 8px',
                borderRadius: 6,
                background: 'var(--surface-2)',
                border: '1px solid var(--line)',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                color: 'var(--ink-2)',
              }}>
                [{artifactTypeLabels[a.type] ?? a.type}] {a.title.slice(0, 24)}
              </span>
            ))}
            {artifacts.length > 4 && (
              <span style={{
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                color: 'var(--ink-2)',
                padding: '3px 6px',
              }}>
                +{artifacts.length - 4}
              </span>
            )}
          </div>
        )}

        {(onRetry || onResume || onCancel) && (
          <div style={{
            display: 'flex',
            gap: 8,
            marginTop: 10,
          }}>
            {onRetry && (
              <WorkAction onClick={onRetry} icon={<RotateCcw size={12} />} label="retry" />
            )}
            {onResume && (
              <WorkAction onClick={onResume} icon={<Play size={12} />} label="resume" />
            )}
            {onCancel && (
              <WorkAction
                onClick={onCancel}
                icon={<X size={12} />}
                label="cancel"
                danger
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusPill({ status }: { status: WorkStatus }) {
  const cfg = STATUS_CONFIG[status]
  const isAnimated = status === 'working'
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '2px 8px',
      borderRadius: 999,
      background: cfg.bg,
      color: cfg.color,
      fontSize: 11,
      fontWeight: 500,
      fontFamily: 'var(--font-body)',
    }}>
      <span style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: cfg.color,
        flexShrink: 0,
        ...(isAnimated ? { animation: 'throb 1.1s ease-in-out infinite' } : {}),
      }} />
      {cfg.label}
    </span>
  )
}

function WorkAction({ onClick, icon, label, danger }: {
  onClick: () => void
  icon: ReactNode
  label: string
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        border: `1px solid ${danger ? 'var(--c-red)' : 'var(--line)'}`,
        borderRadius: 8,
        padding: '4px 10px',
        background: 'transparent',
        cursor: 'pointer',
        color: danger ? 'var(--c-red)' : 'var(--ink)',
        fontSize: 12,
        fontFamily: 'var(--font-body)',
        fontWeight: 500,
      }}
    >
      {icon}
      {label}
    </button>
  )
}
