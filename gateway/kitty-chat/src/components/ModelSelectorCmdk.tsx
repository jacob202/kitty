'use client'

import { useState, useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { Command } from 'cmdk'
import type { Model } from '@/lib/types'

interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  modelFromGateway?: boolean
}

export function ModelSelectorCmdk({ activeModel, models, onSelectModel, modelFromGateway = true }: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  useEffect(() => {
    if (!open) setSearch('')
  }, [open])

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={`Model: ${activeModel.name}`}
        style={{
          ...chipBtnStyle,
          display: 'flex', alignItems: 'center', gap: 6,
        }}
      >
        <span
          title={modelFromGateway ? undefined : 'using offline model list'}
          style={{
            width: 7, height: 7, borderRadius: 99,
            background: modelFromGateway ? activeModel.color : 'var(--c-red)',
          }}
        />
        {activeModel.name}
      </button>

      {open && (
        <div style={popoverStyle}>
          <Command label="Select model" loop shouldFilter>
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder="search models…"
              autoFocus
              style={inputStyle}
            />
            <Command.List style={listStyle}>
              <Command.Empty style={emptyStyle}>no matches</Command.Empty>
              {models.map((m) => (
                <Command.Item
                  key={m.id}
                  value={m.name}
                  onSelect={() => {
                    onSelectModel(m)
                    setOpen(false)
                  }}
                  style={{
                    ...itemStyle,
                    background: m.id === activeModel.id ? 'var(--ginger-fade)' : undefined,
                  }}
                  data-selected={m.id === activeModel.id || undefined}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: 7, height: 7, borderRadius: 99,
                      background: m.color, flexShrink: 0,
                    }}
                  />
                  <span style={{ flex: 1 }}>{m.name}</span>
                  <span style={idStyle}>{m.id}</span>
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </div>
      )}
    </div>
  )
}

const chipBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  border: '1.5px solid var(--line)',
  borderRadius: 8,
  padding: '4px 9px',
  background: 'transparent',
  cursor: 'pointer',
}

const popoverStyle: CSSProperties = {
  position: 'absolute',
  top: 'calc(100% + 6px)',
  right: 0,
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  borderRadius: 12,
  minWidth: 260,
  zIndex: 100,
  boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  overflow: 'hidden',
}

const inputStyle: CSSProperties = {
  width: '100%',
  padding: '10px 14px',
  border: 'none',
  borderBottom: '1px solid var(--line)',
  background: 'transparent',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--ink)',
  outline: 'none',
}

const listStyle: CSSProperties = {
  padding: 6,
  maxHeight: 280,
  overflowY: 'auto',
}

const emptyStyle: CSSProperties = {
  padding: '12px 14px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  textAlign: 'center',
}

const itemStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  width: '100%',
  padding: '8px 12px',
  borderRadius: 8,
  border: 'none',
  cursor: 'pointer',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 500,
  color: 'var(--ink)',
}

const idStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--ink-2)',
  opacity: 0.7,
}
