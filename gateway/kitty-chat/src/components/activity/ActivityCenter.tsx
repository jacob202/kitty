import { useEffect, type CSSProperties } from 'react'
import { X } from 'lucide-react'

import type { GatewayActivityItem, GatewayActivityProjection, GatewayActivityState } from '@/lib/gateway'
import { describeFailure } from '@/lib/failure-copy'

const GROUPS: Array<{ state: GatewayActivityState; label: string }> = [
  { state: 'waiting', label: 'Needs you' },
  { state: 'running', label: 'In motion' },
  { state: 'failed', label: 'Needs repair' },
  { state: 'completed', label: 'Recently finished' },
]

export function ActivityCenter({
  open,
  projection,
  isLoading,
  error,
  onClose,
  onNavigate,
}: {
  open: boolean
  projection?: GatewayActivityProjection
  isLoading: boolean
  error: unknown
  onClose: () => void
  onNavigate: (view: string) => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  const unavailable = Object.entries(projection?.sources ?? {}).filter(([, source]) => source.state === 'unavailable')

  return (
    <div style={backdropStyle} onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
      <section role="dialog" aria-modal="true" aria-label="Activity" style={panelStyle}>
        <header style={headerStyle}>
          <div>
            <div style={eyebrowStyle}>live work</div>
            <h2 style={titleStyle}>Activity</h2>
            <p style={subtitleStyle}>What Kitty is doing, what needs you, and what just finished.</p>
          </div>
          <button type="button" aria-label="Close activity" onClick={onClose} style={closeStyle}><X size={18} /></button>
        </header>

        <div style={bodyStyle}>
          {isLoading && !projection && <p style={mutedStyle}>Reading Kitty activity…</p>}
          {Boolean(error) && !projection && <p role="alert" style={errorStyle}>{describeFailure(error)}</p>}
          {unavailable.length > 0 && (
            <div role="status" style={warningStyle}>
              <strong>Some activity sources are unavailable.</strong>
              {unavailable.map(([name, source]) => <div key={name}>{name}: {source.reason ?? 'unavailable'}</div>)}
            </div>
          )}
          {projection && projection.items.length === 0 && <p style={mutedStyle}>No recent activity.</p>}
          {projection && GROUPS.map(group => {
            const items = projection.items.filter(item => item.state === group.state)
            if (!items.length) return null
            return (
              <section key={group.state} aria-label={group.label} style={groupStyle}>
                <div style={groupHeaderStyle}>
                  <h3 style={groupTitleStyle}>{group.label}</h3>
                  <span style={countStyle}>{items.length}</span>
                </div>
                <div style={listStyle}>{items.map(item => <ActivityRow key={item.id} item={item} onNavigate={onNavigate} />)}</div>
              </section>
            )
          })}
        </div>
      </section>
    </div>
  )
}

function ActivityRow({ item, onNavigate }: { item: GatewayActivityItem; onNavigate: (view: string) => void }) {
  return (
    <article style={rowStyle}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={rowTopStyle}>
          <span style={sourceStyle}>{item.source}</span>
          <span style={rawStyle}>{humanize(item.raw_state)}</span>
        </div>
        <div style={itemTitleStyle}>{item.title}</div>
        {item.detail && <div style={detailStyle}>{item.detail}</div>}
      </div>
      <button type="button" aria-label={`Open ${item.title}`} onClick={() => onNavigate(item.destination)} style={openStyle}>Open</button>
    </article>
  )
}

function humanize(value: string): string {
  return value.replace(/[_-]+/g, ' ')
}

const backdropStyle: CSSProperties = { position: 'fixed', inset: 0, zIndex: 1250, background: 'rgba(0,0,0,0.42)', display: 'flex', justifyContent: 'flex-end' }
const panelStyle: CSSProperties = { width: 'min(520px, 100vw)', height: '100%', background: 'var(--color-background, var(--bg))', borderLeft: '1px solid var(--color-separator, var(--line))', boxShadow: '-20px 0 50px rgba(0,0,0,0.2)', display: 'flex', flexDirection: 'column' }
const headerStyle: CSSProperties = { padding: 18, borderBottom: '1px solid var(--color-separator, var(--line))', display: 'flex', justifyContent: 'space-between', gap: 16 }
const eyebrowStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--color-text-secondary, var(--ink-2))' }
const titleStyle: CSSProperties = { margin: '3px 0 0', fontFamily: 'var(--font-display)', fontSize: 24, color: 'var(--color-text-primary, var(--ink))' }
const subtitleStyle: CSSProperties = { margin: '5px 0 0', fontSize: 12, color: 'var(--color-text-secondary, var(--ink-2))', lineHeight: 1.4 }
const closeStyle: CSSProperties = { width: 44, height: 44, border: '1px solid var(--color-separator, var(--line))', borderRadius: 'var(--r-control, 8px)', background: 'var(--color-surface, var(--surface))', color: 'var(--color-text-primary, var(--ink))', display: 'grid', placeItems: 'center', cursor: 'pointer' }
const bodyStyle: CSSProperties = { flex: 1, minHeight: 0, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 22 }
const mutedStyle: CSSProperties = { margin: 0, color: 'var(--color-text-secondary, var(--ink-2))', fontSize: 13 }
const errorStyle: CSSProperties = { ...mutedStyle, color: 'var(--color-destructive)' }
const warningStyle: CSSProperties = { padding: 12, border: '1px solid var(--color-warning)', borderRadius: 8, fontSize: 11, lineHeight: 1.5, color: 'var(--color-text-secondary, var(--ink-2))' }
const groupStyle: CSSProperties = { display: 'grid', gap: 8 }
const groupHeaderStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between' }
const groupTitleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--color-text-primary, var(--ink))' }
const countStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-text-secondary, var(--ink-2))' }
const listStyle: CSSProperties = { display: 'grid', gap: 7 }
const rowStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 12, padding: 12, border: '1px solid var(--color-separator, var(--line))', borderRadius: 9, background: 'var(--color-surface, var(--surface))' }
const rowTopStyle: CSSProperties = { display: 'flex', gap: 7, alignItems: 'center', marginBottom: 4 }
const sourceStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-accent, var(--primary))' }
const rawStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--color-text-secondary, var(--ink-2))' }
const itemTitleStyle: CSSProperties = { fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary, var(--ink))', overflowWrap: 'anywhere' }
const detailStyle: CSSProperties = { marginTop: 3, fontSize: 11, lineHeight: 1.4, color: 'var(--color-text-secondary, var(--ink-2))', overflowWrap: 'anywhere' }
const openStyle: CSSProperties = { minHeight: 40, border: '1px solid var(--color-separator, var(--line))', borderRadius: 'var(--r-control, 8px)', background: 'transparent', color: 'var(--color-accent, var(--primary))', padding: '7px 10px', fontWeight: 700, cursor: 'pointer', flexShrink: 0 }
