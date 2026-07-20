'use client'
import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { useImageStatus, useImageHistory, useGenerateImage } from '@/lib/queries'

const STYLE_CHIPS = [
  { label: 'portrait',    hint: 'portrait orientation' },
  { label: 'landscape',   hint: 'landscape orientation' },
  { label: 'fast',        hint: 'fewer steps, quicker' },
  { label: 'detailed',    hint: 'more steps, higher quality' },
  { label: 'realistic',   hint: 'SDXL photorealistic' },
  { label: 'more bear',   hint: 'stronger LoRA weight' },
]

type GenState = 'idle' | 'generating' | 'done' | 'error'

export function ImageGenPanel() {
  const statusQuery = useImageStatus()
  const historyQuery = useImageHistory()
  const generate = useGenerateImage()

  const available = statusQuery.data?.available ?? null
  const engines = statusQuery.data?.engines?.length
    ? statusQuery.data.engines
    : [{ name: 'comfyui', label: 'ComfyUI', available: available === true }]
  const history = historyQuery.data ?? []

  const [prompt, setPrompt] = useState('')
  const [chips, setChips] = useState<string[]>([])
  const [engine, setEngine] = useState('comfyui')
  const [state, setState] = useState<GenState>('idle')
  const [errMsg, setErrMsg] = useState('')

  useEffect(() => {
    if (!engines.some(item => item.name === engine && item.available)) {
      const firstAvailable = engines.find(item => item.available)
      if (firstAvailable) setEngine(firstAvailable.name)
    }
  }, [engine, engines])

  function toggleChip(label: string) {
    setChips(prev =>
      prev.includes(label) ? prev.filter(c => c !== label) : [...prev, label]
    )
  }

  function buildPrompt(): string {
    const extras = chips.join(', ')
    return extras ? `${prompt.trim()}, ${extras}` : prompt.trim()
  }

  function handleGenerate() {
    const full = buildPrompt()
    if (!full || state === 'generating') return
    setState('generating')
    setErrMsg('')
    generate.mutate(engine === 'comfyui' ? full : { prompt: full, engine }, {
      onSuccess: result => {
        if (!result) {
          setState('error')
          setErrMsg('generation failed — is ComfyUI running?')
          return
        }
        setState('done')
      },
      onError: () => {
        setState('error')
        setErrMsg('generation failed — is ComfyUI running?')
      },
    })
  }

  if (statusQuery.isPending) {
    return (
      <div style={unavailableStyle} role="status">
        <p style={unavailableTitleStyle}>checking ComfyUI…</p>
        <p style={unavailableBodyStyle}>Checking the configured image renderer before enabling generation.</p>
      </div>
    )
  }

  const availableEngines = engines.filter(item => item.available)
  if (available === false && availableEngines.length === 0) {
    return (
      <div style={unavailableStyle}>
        <p style={unavailableTitleStyle}>
          {statusQuery.data?.engines?.length ? 'image engines offline' : 'ComfyUI offline'}
        </p>
        <p style={unavailableBodyStyle}>
          Start ComfyUI or Draw Things and check again. Kitty reports each configured renderer
          independently; generation stays disabled until at least one engine is reachable.
        </p>
        <button
          type="button"
          onClick={() => void statusQuery.refetch()}
          disabled={statusQuery.isFetching}
          style={retryStyle}
        >
          {statusQuery.isFetching ? 'checking…' : 'check again'}
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div style={engineRowStyle}>
        <label htmlFor="image-engine" style={engineLabelStyle}>engine</label>
        <select
          id="image-engine"
          value={engine}
          onChange={event => setEngine(event.target.value)}
          style={engineSelectStyle}
        >
          {engines.map(item => (
            <option key={item.name} value={item.name} disabled={!item.available}>
              {item.label}{item.available ? '' : ' (offline)'}
            </option>
          ))}
        </select>
        <span style={onlineStyle}>
          {engine}{' '}
          {engines.find(item => item.name === engine)?.available ? 'online' : 'offline'}
        </span>
      </div>

      {/* Prompt input */}
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleGenerate() } }}
        placeholder="describe the image…"
        rows={2}
        style={textareaStyle}
      />

      {/* Style chips */}
      <div style={chipsRowStyle}>
        {STYLE_CHIPS.map(c => (
          <button
            key={c.label}
            onClick={() => toggleChip(c.label)}
            title={c.hint}
            style={{
              ...chipStyle,
              background: chips.includes(c.label) ? 'rgba(232,120,69,0.16)' : 'transparent',
              color: chips.includes(c.label) ? 'var(--cat-ginger)' : 'var(--ink-2)',
              borderColor: chips.includes(c.label) ? 'rgba(232,120,69,0.35)' : 'var(--line)',
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={!prompt.trim() || state === 'generating'}
        style={{ ...genBtnStyle, opacity: !prompt.trim() || state === 'generating' ? 0.4 : 1 }}
      >
        {state === 'generating' ? 'generating…' : 'generate'}
      </button>

      {/* Error */}
      {state === 'error' && <p style={errorStyle}>{errMsg}</p>}

      {/* Image history grid */}
      {history.length > 0 && (
        <div style={gridStyle}>
          {history.map(img => (
            <div key={img.prompt_id} style={thumbWrapStyle}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                // Keep absolute Kitty-store paths in one proxy segment so the
                // catch-all route does not drop the leading slash.
                src={`/proxy/image/view/${encodeURIComponent(img.filename)}`}
                alt={img.prompt}
                style={thumbStyle}
                title={img.prompt}
                loading="lazy"
              />
            </div>
          ))}
        </div>
      )}

      {history.length === 0 && state !== 'generating' && (
        <p style={emptyStyle}>no images yet</p>
      )}
    </div>
  )
}

const textareaStyle: CSSProperties = {
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '6px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
  outline: 'none',
  resize: 'vertical',
  lineHeight: 1.5,
}

const engineRowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
}

const engineLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
  textTransform: 'lowercase',
}

const engineSelectStyle: CSSProperties = {
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '4px 7px',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const chipsRowStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

const chipStyle: CSSProperties = {
  padding: '3px 8px',
  border: '1px solid var(--line)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  cursor: 'pointer',
}

const genBtnStyle: CSSProperties = {
  padding: '6px 12px',
  background: 'rgba(232,120,69,0.12)',
  border: '1px solid rgba(232,120,69,0.3)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--cat-ginger)',
  cursor: 'pointer',
  textAlign: 'left',
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gap: 5,
}

const thumbWrapStyle: CSSProperties = {
  aspectRatio: '1',
  overflow: 'hidden',
  borderRadius: 4,
  border: '1px solid var(--line)',
  background: 'var(--surface-2)',
}

const thumbStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
}

const errorStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--cat-ginger)',
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
}

const unavailableStyle: CSSProperties = {
  padding: '10px 12px',
  background: 'var(--surface-2)',
  border: '1px solid var(--line)',
  borderRadius: 4,
}

const unavailableTitleStyle: CSSProperties = {
  margin: '0 0 4px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
}

const unavailableBodyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
  lineHeight: 1.5,
}

const retryStyle: CSSProperties = {
  marginTop: 10,
  padding: '5px 9px',
  background: 'transparent',
  border: '1px solid var(--line)',
  borderRadius: 4,
  color: 'var(--ink-2)',
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
}

const onlineStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--c-blue)',
  textTransform: 'lowercase',
}
