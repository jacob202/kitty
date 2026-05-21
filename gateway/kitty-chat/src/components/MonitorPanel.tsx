'use client'
import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { fetchGatewayMonitors, addGatewayMonitor, removeGatewayMonitor, type GatewayMonitor } from '@/lib/gateway'

export function MonitorPanel() {
  const [monitors, setMonitors] = useState<GatewayMonitor[]>([])
  const [url, setUrl] = useState('')
  const [label, setLabel] = useState('')
  const [adding, setAdding] = useState(false)
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    void load()
    const id = setInterval(() => void load(), 60000)
    return () => clearInterval(id)
  }, [])

  async function load() {
    const list = await fetchGatewayMonitors()
    setMonitors(list)
  }

  async function handleAdd() {
    const u = url.trim()
    const l = label.trim() || u
    if (!u || adding) return
    setAdding(true)
    const id = await addGatewayMonitor(u, l)
    setAdding(false)
    if (id) {
      setUrl(''); setLabel(''); setShowForm(false)
      await load()
    }
  }

  async function handleRemove(id: string) {
    await removeGatewayMonitor(id)
    await load()
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {monitors.length > 0 ? (
        <div style={{ display: 'grid', gap: 5 }}>
          {monitors.map(m => (
            <div key={m.watch_id} style={rowStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={labelStyle}>{m.label}</span>
                <span style={{ ...statusStyle, color: m.match_count > 0 ? 'var(--orange)' : 'var(--text-faint)' }}>
                  {m.match_count > 0 ? `${m.match_count} hits` : 'watching'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <span style={urlStyle}>{m.url.replace(/^https?:\/\//, '').slice(0, 40)}</span>
                <button onClick={() => void handleRemove(m.watch_id)} style={removeButtonStyle}>×</button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={emptyStyle}>no monitors yet</p>
      )}

      {showForm ? (
        <div style={{ display: 'grid', gap: 5 }}>
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://…"
            style={inputStyle}
          />
          <input
            value={label}
            onChange={e => setLabel(e.target.value)}
            placeholder="label (optional)"
            style={inputStyle}
          />
          <div style={{ display: 'flex', gap: 5 }}>
            <button onClick={() => void handleAdd()} disabled={!url.trim() || adding}
              style={{ ...actionButtonStyle, opacity: !url.trim() || adding ? 0.4 : 1 }}>
              {adding ? '…' : 'add'}
            </button>
            <button onClick={() => { setShowForm(false); setUrl(''); setLabel('') }} style={cancelButtonStyle}>
              cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setShowForm(true)} style={addButtonStyle}>+ add monitor</button>
      )}
    </div>
  )
}

const rowStyle: CSSProperties = {
  padding: '6px 8px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  display: 'grid',
  gap: 3,
}

const labelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
}

const statusStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
}

const urlStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-muted)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const removeButtonStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--text-faint)',
  cursor: 'pointer',
  fontSize: 13,
  padding: '0 4px',
  lineHeight: 1,
  flexShrink: 0,
}

const inputStyle: CSSProperties = {
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  padding: '5px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
}

const actionButtonStyle: CSSProperties = {
  flex: 1,
  padding: '5px 10px',
  background: 'rgba(232,120,69,0.15)',
  border: '1px solid rgba(232,120,69,0.3)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--orange-2)',
  cursor: 'pointer',
}

const cancelButtonStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'transparent',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
  cursor: 'pointer',
}

const addButtonStyle: CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  padding: '5px 10px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  textAlign: 'left',
}

const emptyStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
}
