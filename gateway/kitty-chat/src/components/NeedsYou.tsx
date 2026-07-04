'use client'
import type { CSSProperties } from 'react'
import type { GatewayAction, GatewayTriageEntry } from '@/lib/gateway'
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState, bodyText } from '@/lib/ui'
import { Skeleton } from './Skeleton'

interface Props {
  actions: GatewayAction[]
  actionsLoading?: boolean
  actionsError: string | null
  needsJacob: GatewayTriageEntry[]
  needsJacobLoading?: boolean
  needsJacobError: string | null
  busyActionId?: number | null
  onApprove: (actionId: number) => void
  onReject: (actionId: number) => void
  onDecideInChat: (entry: GatewayTriageEntry) => void
}

export function NeedsYou({
  actions,
  actionsLoading = false,
  actionsError,
  needsJacob,
  needsJacobLoading = false,
  needsJacobError,
  busyActionId = null,
  onApprove,
  onReject,
  onDecideInChat,
}: Props) {
  const total = actions.length + needsJacob.length
  const loading = actionsLoading || needsJacobLoading
  const bothErrored = Boolean(actionsError) && Boolean(needsJacobError)

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>Needs you</span>
        <span style={countStyle}>{total} open</span>
      </div>

      {bothErrored ? (
        <div style={errorStyle} role="alert">
          Can&apos;t reach the gateway ({actionsError}). Nothing to approve until it&apos;s back.
        </div>
      ) : (
        <div style={listStyle}>
          {actionsError && (
            <div style={errorStyle} role="alert">Actions unavailable ({actionsError}).</div>
          )}
          {actions.map((action) => (
            <div key={action.id} style={itemStyle}>
              <div style={itemHeaderStyle}>
                <span style={itemTitleStyle}>{action.title}</span>
                <span style={tierBadgeStyle(action.risk_tier)}>{action.risk_tier}</span>
              </div>
              <div style={previewStyle}>{action.preview}</div>
              <div style={actionRowStyle}>
                <button
                  type="button"
                  disabled={busyActionId === action.id}
                  onClick={() => onApprove(action.id)}
                  style={approveBtnStyle}
                >
                  approve
                </button>
                <button
                  type="button"
                  disabled={busyActionId === action.id}
                  onClick={() => onReject(action.id)}
                  style={rejectBtnStyle}
                >
                  reject
                </button>
              </div>
            </div>
          ))}

          {needsJacobError && (
            <div style={errorStyle} role="alert">Triage queue unavailable ({needsJacobError}).</div>
          )}
          {needsJacob.map((entry) => (
            <div key={entry.inbox_id} style={itemStyle}>
              <div style={itemHeaderStyle}>
                <span style={itemTitleStyle}>needs a decision</span>
                <span style={needsJacobBadgeStyle}>ambiguous</span>
              </div>
              {entry.text && <div style={previewStyle}>{entry.text.slice(0, 160)}</div>}
              {entry.rationale && <div style={rationaleStyle}>{entry.rationale}</div>}
              <div style={actionRowStyle}>
                <button
                  type="button"
                  onClick={() => onDecideInChat(entry)}
                  style={approveBtnStyle}
                >
                  decide in chat
                </button>
              </div>
            </div>
          ))}

          {total === 0 && !actionsError && !needsJacobError && (
            loading ? (
              <div style={{ display: 'grid', gap: 8 }}>
                <Skeleton height={64} />
                <Skeleton height={64} />
              </div>
            ) : (
              <div style={emptyStyle}>Nothing needs you right now.</div>
            )
          )}
        </div>
      )}
    </div>
  )
}

const containerStyle: CSSProperties = { ...card, display: 'flex', flexDirection: 'column', gap: 12 }
const headerStyle: CSSProperties = cardHeader
const titleStyle: CSSProperties = cardTitle
const countStyle: CSSProperties = cardMeta

const listStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8 }

const itemStyle: CSSProperties = { ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }

const itemHeaderStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}

const itemTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
}

const previewStyle: CSSProperties = { ...bodyText }

const rationaleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
}

const badgeBaseStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  border: '1px solid',
  borderRadius: 4,
  padding: '2px 6px',
  background: 'transparent',
}

function tierBadgeStyle(tier: GatewayAction['risk_tier']): CSSProperties {
  const color = tier === 'T2' ? 'var(--error)' : tier === 'T1' ? 'var(--orange)' : 'var(--mint)'
  return { ...badgeBaseStyle, color, borderColor: color }
}

const needsJacobBadgeStyle: CSSProperties = {
  ...badgeBaseStyle,
  color: 'var(--orange)',
  borderColor: 'var(--orange)',
}

const actionRowStyle: CSSProperties = { display: 'flex', gap: 8, marginTop: 2 }

const btnBaseStyle: CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 4,
  padding: '5px 12px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.04em',
  cursor: 'pointer',
  background: 'var(--surface-mid)',
  color: 'var(--text)',
}

const approveBtnStyle: CSSProperties = { ...btnBaseStyle, color: 'var(--mint)', borderColor: 'var(--mint)' }
const rejectBtnStyle: CSSProperties = { ...btnBaseStyle, color: 'var(--text-muted)' }

const errorStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--error)',
  padding: '8px 0',
}

const emptyStyle: CSSProperties = emptyState
