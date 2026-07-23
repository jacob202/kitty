'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Command } from 'cmdk'
import { Zap, Shield, DollarSign, Cpu, Lock, Globe, Brain } from 'lucide-react'
import type { Model } from '@/lib/types'

interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  modelFromGateway?: boolean
}

interface ModelMeta {
  id: string
  name: string
  color: string
  glow: string
  provider: string
  capabilities: string[]
  costPer1kTokens?: { input: number; output: number }
  privacyTier: 'local' | 'private' | 'standard' | 'cloud' | 'auto'
  contextWindow: number
  description: string
}

// Model metadata - in real app this could come from gateway
const MODEL_METADATA: Record<string, ModelMeta> = {
  'claude-sonnet-4-6': {
    id: 'claude-sonnet-4-6',
    name: 'sonnet-4',
    color: '#a884ff',
    glow: '#a884ff99',
    provider: 'Anthropic',
    capabilities: ['reasoning', 'coding', 'analysis', 'writing'],
    costPer1kTokens: { input: 0.003, output: 0.015 },
    privacyTier: 'cloud',
    contextWindow: 200000,
    description: 'Balanced reasoning and speed. Best for most tasks.',
  },
  'claude-opus-4-7': {
    id: 'claude-opus-4-7',
    name: 'opus-4',
    color: '#21bdd9',
    glow: '#21bdd999',
    provider: 'Anthropic',
    capabilities: ['deep-reasoning', 'complex-coding', 'analysis', 'creative'],
    costPer1kTokens: { input: 0.015, output: 0.075 },
    privacyTier: 'cloud',
    contextWindow: 200000,
    description: 'Most capable model. Best for complex reasoning and creative tasks.',
  },
  'claude-haiku-4-5': {
    id: 'claude-haiku-4-5',
    name: 'haiku-4',
    color: '#9be86b',
    glow: '#9be86b99',
    provider: 'Anthropic',
    capabilities: ['fast-response', 'simple-coding', 'classification'],
    costPer1kTokens: { input: 0.00025, output: 0.00125 },
    privacyTier: 'cloud',
    contextWindow: 200000,
    description: 'Fast and cheap. Best for high-volume simple tasks.',
  },
  'gpt-4o': {
    id: 'gpt-4o',
    name: 'gpt-4o',
    color: '#f4c542',
    glow: '#f4c54299',
    provider: 'OpenAI',
    capabilities: ['multimodal', 'coding', 'analysis', 'vision'],
    costPer1kTokens: { input: 0.005, output: 0.015 },
    privacyTier: 'cloud',
    contextWindow: 128000,
    description: 'Multimodal model with vision. Good for image analysis.',
  },
  'deepseek-v3': {
    id: 'deepseek-v3',
    name: 'deepseek',
    color: '#ff5577',
    glow: '#ff557799',
    provider: 'DeepSeek',
    capabilities: ['coding', 'math', 'reasoning', 'chinese'],
    costPer1kTokens: { input: 0.00014, output: 0.00028 },
    privacyTier: 'cloud',
    contextWindow: 64000,
    description: 'Strong coding and math. Very cost-effective.',
  },
  'kitty-default': {
    id: 'kitty-default',
    name: 'default',
    color: '#888',
    glow: '#88888899',
    provider: 'Auto',
    capabilities: ['auto-routing'],
    privacyTier: 'auto',
    contextWindow: 0,
    description: 'Automatically selects best model based on task type.',
  },
}

export function ModelSelectorCmdk({ 
  activeModel, 
  models, 
  onSelectModel, 
  modelFromGateway = true 
}: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [hoveredModel, setHoveredModel] = useState<ModelMeta | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Build model metadata map
  const modelsWithMeta = useMemo(() => {
    return models.map(m => ({
      ...m,
      meta: MODEL_METADATA[m.id] || { 
        ...m, 
        provider: 'Unknown',
        capabilities: [],
        privacyTier: 'cloud',
        contextWindow: 0,
        description: 'No metadata available',
      }
    }))
  }, [models])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false)
        setHoveredModel(null)
      }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  useEffect(() => {
    if (!open) setSearch('')
  }, [open])

  const getPrivacyLabel = (tier: string) => {
    switch (tier) {
      case 'local': return { label: 'Local only', icon: Lock, color: 'var(--cat-green)' }
      case 'private': return { label: 'Private cloud', icon: Shield, color: 'var(--c-blue)' }
      case 'standard': return { label: 'Standard cloud', icon: Globe, color: 'var(--c-yellow)' }
      case 'cloud': return { label: 'Cloud', icon: Globe, color: 'var(--c-red)' }
      case 'auto': return { label: 'Auto-routed', icon: Brain, color: 'var(--c-purple)' }
      default: return { label: tier, icon: Globe, color: 'var(--ink-2)' }
    }
  }

  const getCapabilityIcon = (cap: string) => {
    switch (cap) {
      case 'reasoning':
      case 'deep-reasoning': return Brain
      case 'coding':
      case 'complex-coding':
      case 'simple-coding': return Cpu
      case 'multimodal':
      case 'vision': return Globe
      case 'analysis': return Brain
      case 'writing':
      case 'creative': return Brain
      case 'math': return Cpu
      case 'chinese': return Globe
      case 'fast-response': return Zap
      case 'auto-routing': return Brain
      default: return Cpu
    }
  }

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
          <div style={{ display: 'flex', flexDirection: 'row', gap: 12, minWidth: 420 }}>
            {/* Model list */}
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
                {modelsWithMeta
                  .filter(m => m.name.toLowerCase().includes(search.toLowerCase()))
                  .map((m) => (
                  <Command.Item
                    key={m.id}
                    value={m.name}
                    onSelect={() => {
                      onSelectModel(m)
                      setOpen(false)
                      setHoveredModel(null)
                    }}
                    onMouseEnter={() => setHoveredModel(m.meta)}
                    onMouseLeave={() => setHoveredModel(null)}
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

            {/* Hover preview panel */}
            {hoveredModel && (
              <ModelPreviewPanel model={hoveredModel} getPrivacyLabel={getPrivacyLabel} getCapabilityIcon={getCapabilityIcon} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ModelPreviewPanel({ 
  model, 
  getPrivacyLabel, 
  getCapabilityIcon 
}: { 
  model: ModelMeta
  getPrivacyLabel: (tier: string) => { label: string; icon: React.ComponentType<{ size?: number }>; color: string }
  getCapabilityIcon: (cap: string) => React.ComponentType<{ size?: number }>
}) {
  const privacy = getPrivacyLabel(model.privacyTier)
  const PrivacyIcon = privacy.icon

  return (
    <div style={previewPanelStyle}>
      <div style={previewHeaderStyle}>
        <span
          style={{
            width: 12, height: 12, borderRadius: 99,
            background: model.color, flexShrink: 0,
          }}
        />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>
            {model.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)' }}>
            {model.provider} · {model.id}
          </div>
        </div>
      </div>

      <div style={previewSectionStyle}>
        <div style={previewSectionTitleStyle}>Description</div>
        <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.5 }}>
          {model.description}
        </div>
      </div>

      <div style={previewSectionStyle}>
        <div style={previewSectionTitleStyle}>Capabilities</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {model.capabilities.map(cap => {
            const Icon = getCapabilityIcon(cap)
            return (
              <span key={cap} style={capabilityBadgeStyle}>
                <span style={{ color: 'var(--primary)', display: 'flex' }}>
                  <Icon size={10} />
                </span>
                {cap.charAt(0).toUpperCase() + cap.slice(1).replace(/-/g, ' ')}
              </span>
            )
          })}
        </div>
      </div>

      <div style={previewSectionStyle}>
        <div style={previewSectionTitleStyle}>Privacy & Routing</div>
        <div style={privacyRowStyle}>
          <span style={{ color: privacy.color, display: 'flex' }}>
            <PrivacyIcon size={14} />
          </span>
          <span style={{ fontSize: 12, color: privacy.color, fontWeight: 500 }}>
            {privacy.label}
          </span>
          <span style={{ fontSize: 10, color: 'var(--ink-2)', marginLeft: 'auto' }}>
            {model.privacyTier === 'auto' ? 'Routes based on content' : 'Data sent to provider'}
          </span>
        </div>
      </div>

      {model.costPer1kTokens && (
        <div style={previewSectionStyle}>
          <div style={previewSectionTitleStyle}>Cost (per 1K tokens)</div>
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--ink-2)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <DollarSign size={10} />
              Input: ${model.costPer1kTokens.input.toFixed(4)}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <DollarSign size={10} />
              Output: ${model.costPer1kTokens.output.toFixed(4)}
            </span>
          </div>
        </div>
      )}

      <div style={previewSectionStyle}>
        <div style={previewSectionTitleStyle}>Context Window</div>
        <div style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          {model.contextWindow > 0 
            ? `${(model.contextWindow / 1000).toFixed(0)}K tokens`
            : 'Dynamic'}
        </div>
      </div>
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
  maxHeight: 320,
  overflowY: 'auto',
  flex: 1,
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

const previewPanelStyle: CSSProperties = {
  width: 240,
  padding: 16,
  background: 'var(--surface-2)',
  borderLeft: '1px solid var(--line)',
  display: 'flex',
  flexDirection: 'column',
  gap: 16,
  overflowY: 'auto',
}

const previewHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 10,
}

const previewSectionStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

const previewSectionTitleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'lowercase',
  color: 'var(--ink-2)',
}

const capabilityBadgeStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  fontSize: 10,
  fontFamily: 'var(--font-mono)',
  color: 'var(--ink-2)',
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  borderRadius: 99,
  padding: '2px 8px',
}

const privacyRowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 11,
}

export { chipBtnStyle, popoverStyle, inputStyle, listStyle, emptyStyle, itemStyle, idStyle }