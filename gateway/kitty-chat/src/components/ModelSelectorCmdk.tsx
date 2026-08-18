'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import type { CSSProperties } from 'react'
import { Command } from 'cmdk'
import type { Model } from '@/lib/types'
import { buildPickerModels, fetchModelPicker } from '@/lib/model-picker'

interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  modelFromGateway?: boolean
  /** Phone header: the model name can otherwise push the neighbouring controls
   *  off-screen, so the trigger chip truncates instead of growing. */
  compact?: boolean
}

export function ModelSelectorCmdk({ activeModel, models, onSelectModel, modelFromGateway = true, compact = false }: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [curatedModels, setCuratedModels] = useState<Model[] | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!modelFromGateway) {
      setCuratedModels(null)
      setOpen(false)
      return
    }
    const controller = new AbortController()
    void fetchModelPicker(controller.signal)
      .then(payload => {
        const curated = buildPickerModels(payload)
        if (curated.length > 0) setCuratedModels(curated)
      })
      .catch(() => {
        // The caller's runtime-backed model list remains the honest fallback.
      })
    return () => controller.abort()
  }, [modelFromGateway])

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

  const visibleModels = useMemo(() => {
    if (!curatedModels) return models
    const curatedByRoute = new Map(curatedModels.map(model => [model.id, model]))
    // Runtime-backed choices are authoritative. Curated picker data may add
    // decision metadata to those routes, but it cannot introduce a route the
    // app does not currently consider available.
    return models.map(model => curatedByRoute.get(model.id) ?? model)
  }, [curatedModels, models])

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={!modelFromGateway}
        title={modelFromGateway ? undefined : 'model availability is unknown — reconnect to Kitty before switching'}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={`Model: ${activeModel.name}`}
        style={{
          ...chipBtnStyle,
          display: 'flex', alignItems: 'center', gap: 6,
          opacity: modelFromGateway ? 1 : 0.65,
          cursor: modelFromGateway ? 'pointer' : 'not-allowed',
        }}
      >
        <span
          style={{
            width: 7, height: 7, borderRadius: 99,
            background: modelFromGateway ? activeModel.color : 'var(--c-red)',
            flexShrink: 0,
          }}
        />
        <span style={compact ? compactLabelStyle : undefined}>{activeModel.name}</span>
      </button>

      {open && modelFromGateway && (
        <div style={popoverStyle}>
          <Command label="Select model" loop shouldFilter>
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder="search the shortlist…"
              autoFocus
              style={inputStyle}
            />
            <Command.List style={listStyle}>
              <Command.Empty style={emptyStyle}>
                {visibleModels.length === 0 ? 'no live models available' : 'no matches'}
              </Command.Empty>
              {visibleModels.map((m) => (
                <Command.Item
                  key={m.id}
                  value={`${m.name} ${m.upstreamModel ?? ''} ${m.provider ?? ''} ${m.purpose ?? ''}`}
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
                      background: m.color, flexShrink: 0, marginTop: 5,
                    }}
                  />
                  <span style={{ display: 'grid', gap: 2, flex: 1, minWidth: 0 }}>
                    <span style={{ display: 'flex', gap: 8, alignItems: 'baseline', minWidth: 0 }}>
                      <span style={{ fontWeight: 650 }}>{m.name}</span>
                      <span style={providerChipStyle}>{providerLabel(m)}</span>
                    </span>
                    {m.purpose && <span style={purposeStyle}>{m.purpose}</span>}
                    <span style={decisionRowStyle}>
                      <span>{m.upstreamModel ?? 'automatic route'}</span>
                      {formatContext(m.contextLength) && <span>{formatContext(m.contextLength)}</span>}
                      {formatPrice(m) && <span>{formatPrice(m)}</span>}
                    </span>
                  </span>
                </Command.Item>
              ))}
            </Command.List>
            <div style={footerStyle}>
              curated choices · exact provider facts only when known
            </div>
          </Command>
        </div>
      )}
    </div>
  )
}

function formatContext(contextLength?: number | null): string | null {
  if (!contextLength || contextLength <= 0) return null
  if (contextLength >= 1_000_000) return `${(contextLength / 1_000_000).toFixed(contextLength % 1_000_000 === 0 ? 0 : 1)}m context`
  if (contextLength >= 1_000) return `${Math.round(contextLength / 1_000)}k context`
  return `${contextLength} context`
}

function formatPrice(model: Model): string | null {
  const input = model.inputUsdPerMillion
  const output = model.outputUsdPerMillion
  if (input == null && output == null) return null
  const money = (value: number | null | undefined) => value == null ? '?' : `$${value.toFixed(2)}`
  return `${money(input)} in · ${money(output)} out / 1m`
}

function providerLabel(model: Model): string {
  if (model.provider) return model.provider === 'openrouter' ? 'OpenRouter' : model.provider
  if (!model.upstreamModel) return 'auto'
  const prefix = model.upstreamModel.split('/')[0]?.toLowerCase() ?? ''
  const labels: Record<string, string> = {
    openrouter: 'OpenRouter', openai: 'OpenAI', google: 'Google', gemini: 'Gemini',
    anthropic: 'Anthropic', deepseek: 'DeepSeek', nvidia: 'NVIDIA', local: 'local',
  }
  return labels[prefix] ?? prefix
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

const compactLabelStyle: CSSProperties = {
  maxWidth: 140,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const popoverStyle: CSSProperties = {
  position: 'absolute',
  top: 'calc(100% + 6px)',
  right: 0,
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  borderRadius: 12,
  minWidth: 360,
  maxWidth: 'min(440px, calc(100vw - 24px))',
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
  maxHeight: 360,
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
  alignItems: 'flex-start',
  gap: 10,
  width: '100%',
  padding: '9px 12px',
  borderRadius: 8,
  border: 'none',
  cursor: 'pointer',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--ink)',
}

const providerChipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.04em',
  padding: '1px 5px', borderRadius: 999, border: '1px solid var(--line)',
  color: 'var(--ink-2)', flexShrink: 0,
}

const purposeStyle: CSSProperties = {
  fontFamily: 'var(--font-body)', fontSize: 11, lineHeight: 1.35, color: 'var(--ink-2)',
}

const decisionRowStyle: CSSProperties = {
  display: 'flex', flexWrap: 'wrap', gap: '3px 10px', fontFamily: 'var(--font-mono)',
  fontSize: 9, color: 'var(--ink-2)', opacity: 0.8,
}

const footerStyle: CSSProperties = {
  borderTop: '1px solid var(--line)', padding: '7px 12px', fontFamily: 'var(--font-mono)',
  fontSize: 9, color: 'var(--ink-2)',
}
