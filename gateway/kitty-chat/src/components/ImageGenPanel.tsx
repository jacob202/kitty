'use client'
import { useState } from 'react'
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
  const history = historyQuery.data ?? []

  const [prompt, setPrompt] = useState('')
  const [chips, setChips] = useState<string[]>([])
  const [state, setState] = useState<GenState>('idle')
  const [errMsg, setErrMsg] = useState('')

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
    generate.mutate(full, {
      onSuccess: result => {
        if (!result) {
          setState('error')
          setErrMsg('Generation failed — is ComfyUI running?')
          return
        }
        setState('done')
      },
      onError: () => {
        setState('error')
        setErrMsg('Generation failed — is ComfyUI running?')
      },
    })
  }

  if (available === false) {
    return (
      <div style={unavailableStyle}>
        <p style={unavailableTitleStyle}>ComfyUI offline</p>
        <p style={unavailableBodyStyle}>
          Start the Colab notebook and set COMFY_URL in .env, then restart the gateway.
        </p>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {available === true && <p style={onlineStyle}>comfyui online</p>}

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
              color: chips.includes(c.label) ? 'var(--orange-2)' : 'var(--text-muted)',
              borderColor: chips.includes(c.label) ? 'rgba(232,120,69,0.35)' : 'var(--border-dim)',
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
                src={`/proxy/image/view/${img.filename}`}
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
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 4,
  padding: '6px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
  resize: 'vertical',
  lineHeight: 1.5,
}

const chipsRowStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

const chipStyle: CSSProperties = {
  padding: '3px 8px',
  border: '1px solid var(--border-dim)',
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
  color: 'var(--orange-2)',
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
  border: '1px solid var(--border-dim)',
  background: 'var(--recessed)',
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
  color: 'var(--orange)',
}

const emptyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
}

const unavailableStyle: CSSProperties = {
  padding: '10px 12px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 4,
}

const unavailableTitleStyle: CSSProperties = {
  margin: '0 0 4px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
}

const unavailableBodyStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-faint)',
  lineHeight: 1.5,
}

const onlineStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--teal)',
  textTransform: 'lowercase',
}
