'use client'
import { useEffect, useState, useRef, useCallback } from 'react'
import { Image, User, Sparkles, Zap, Shield, ChevronDown, X, Upload, Plus, AlertTriangle, CheckCircle2, RefreshCw, Square } from 'lucide-react'
import { useImageStatus } from '@/lib/queries'

interface Character {
  character_id: string
  name: string
  description: string | null
  identity_preset: string
  references: CharacterRef[]
}

interface CharacterRef {
  ref_id: string
  is_primary: boolean
  original_name: string | null
  storage_path: string
}

interface Recipe {
  recipe_id: string
  display_name: string
  quality_tier: string
  supports_characters: boolean
  identity_strength: number
  is_available: boolean
}

interface GenerateResult {
  job_id: string
  filename: string
  recipe?: string
  routing_reason?: string
  character_weight?: number
}

interface QualityInfo {
  has_blockers: boolean
  has_warnings: boolean
  is_perfect: boolean
  summary: string
  advice: string[]
  dimensions: string | null
}

type QualityTier = 'fast' | 'quality' | 'maximum'
type IdentityMode = 'creative' | 'balanced' | 'identity_first'

function useStudioCharacters() {
  const [characters, setCharacters] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchChars()
  }, [])

  async function fetchChars() {
    setLoading(true)
    try {
      const r = await fetch('/proxy/studio/characters')
      if (r.ok) {
        const d = await r.json()
        setCharacters(d.characters ?? [])
      }
    } catch { /* offline ok */ }
    setLoading(false)
  }

  async function createChar(name: string) {
    const r = await fetch('/proxy/studio/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!r.ok) throw new Error(await r.text())
    const char = await r.json()
    setCharacters(prev => [char, ...prev])
    return char
  }

  return { characters, loading, createChar, refetch: fetchChars }
}

function useStudioRecipes() {
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchRecipes()
  }, [])

  async function fetchRecipes() {
    setLoading(true)
    try {
      const r = await fetch('/proxy/studio/recipes?available_only=true')
      if (r.ok) {
        const d = await r.json()
        setRecipes(d.recipes ?? [])
      }
    } catch { /* offline ok */ }
    setLoading(false)
  }

  return { recipes, loading, refetch: fetchRecipes }
}

export function ImageStudio() {
  const [prompt, setPrompt] = useState('')
  const [quality, setQuality] = useState<QualityTier>('quality')
  const [identity, setIdentity] = useState<IdentityMode>('balanced')
  const [selectedChar, setSelectedChar] = useState<Character | null>(null)
  const [generating, setGenerating] = useState(false)
  const [results, setResults] = useState<GenerateResult[]>([])
  const [error, setError] = useState('')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)
  const [routingReason, setRoutingReason] = useState('')
  const [showCharPicker, setShowCharPicker] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [seed, setSeed] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [newCharName, setNewCharName] = useState('')
  const [showNewChar, setShowNewChar] = useState(false)
  const [charRefFile, setCharRefFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [refQuality, setRefQuality] = useState<QualityInfo | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null)
  const [planPreviewing, setPlanPreviewing] = useState(false)
  const [guidanceTags, setGuidanceTags] = useState<string[]>([])
  const [availableTags, setAvailableTags] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)

  // Studio must fail closed: when no image engine is reachable, generation must
  // not dispatch a request the backend can only reject (#346).
  const statusQuery = useImageStatus()
  const pendingStatus = statusQuery.isPending
  const statusFailed = statusQuery.isError
  const enginesAvailable = statusQuery.data?.available === true
    || (statusQuery.data?.engines ?? []).some(e => e.available)

  // Fetch available guidance tags on mount.
  useEffect(() => {
    let cancelled = false
    fetch('/proxy/studio/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: '.' }),
    }).then(r => r.json()).then(data => {
      if (!cancelled && Array.isArray(data.available_guidance_tags)) {
        setAvailableTags(data.available_guidance_tags)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { characters, loading: charsLoading, createChar, refetch: refetchChars } = useStudioCharacters()
  const { recipes, loading: recipesLoading } = useStudioRecipes()

  useEffect(() => {
    setIdentity(selectedChar?.identity_preset as IdentityMode ?? 'balanced')
  }, [selectedChar])

  async function handleGenerate() {
    if (!prompt.trim() || generating) return
    // Fail closed: never dispatch an impossible generation request.
    if (!enginesAvailable) {
      setError('no image engine is online — start ComfyUI or Draw Things, then check again')
      return
    }
    setGenerating(true)
    setError('')
    setErrorDetail(null)
    setRoutingReason('')
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const body: Record<string, unknown> = {
        prompt: prompt.trim(), quality, identity,
      }
      if (selectedChar) body.character_id = selectedChar.character_id
      if (negativePrompt.trim()) body.negative_prompt = negativePrompt.trim()

      const r = await fetch('/proxy/studio/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!r.ok) {
        const detail = await r.text()
        throw new Error(detail || `generation failed (${r.status})`)
      }

      const result: GenerateResult = await r.json()
      setResults(prev => [result, ...prev])
      if (result.routing_reason) setRoutingReason(result.routing_reason)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError('generation canceled')
      } else {
        const { message, detail } = friendlyStudioError(err, 'generate')
        setError(message)
        setErrorDetail(detail)
      }
    }
    setGenerating(false)
    setActiveJobId(null)
    abortRef.current = null
  }

  function handleCancel() {
    abortRef.current?.abort()
  }

  async function handlePreviewPlan() {
    if (!prompt.trim() || planPreviewing) return
    // Plan preview hits only the studio planning route, not a renderer, so it
    // stays available while engines are offline.
    setPlanPreviewing(true)
    setError('')
    setErrorDetail(null)
    setPlan(null)

    try {
      const body: Record<string, unknown> = {
        prompt: prompt.trim(),
      }
      if (selectedChar) body.character_id = selectedChar.character_id
      if (guidanceTags.length > 0) body.guidance_tags = guidanceTags

      const r = await fetch('/proxy/studio/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!r.ok) {
        const detail = await r.text()
        throw new Error(detail || `plan preview failed (${r.status})`)
      }

      const result = await r.json()
      setPlan(result)
    } catch (err) {
      const { message, detail } = friendlyStudioError(err, 'plan')
      setError(message)
      setErrorDetail(detail)
    }
    setPlanPreviewing(false)
  }

  const handleCreateCharacter = useCallback(async () => {
    if (!newCharName.trim()) return
    try {
      const char = await createChar(newCharName.trim())
      if (charRefFile && char) {
        setUploading(true)
        const form = new FormData()
        form.append('file', charRefFile)
        const r = await fetch(`/proxy/studio/characters/${char.character_id}/references`, {
          method: 'POST',
          body: form,
        })
        if (r.ok) {
          const refResult = await r.json()
          if (refResult.quality) {
            setRefQuality(refResult.quality)
          }
        } else {
          console.warn('ref upload failed', await r.text())
        }
        setCharRefFile(null)
        setUploading(false)
        refetchChars()
      }
      setNewCharName('')
      setShowNewChar(false)
      setSelectedChar(char)
    } catch (err) {
      const { message, detail } = friendlyStudioError(err, 'character')
      setError(message)
      setErrorDetail(detail)
    }
  }, [newCharName, charRefFile, createChar, refetchChars])

  // Pressing Enter must always be bound to the CURRENT renderer availability. The
  // keydown handler is memoized so 30s status polls don't recreate it; without a
  // live indirection it would keep the online generation closure after a status
  // flip to offline and dispatch an impossible request (PR #355 finding 5). The
  // ref always points at this render's handleGenerate, so Enter fails closed too.
  const handleGenerateRef = useRef(handleGenerate)
  useEffect(() => {
    handleGenerateRef.current = handleGenerate
  }, [handleGenerate])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleGenerateRef.current()
    }
  }, [])

  const selectedIdentityRecipe = recipes.find(r =>
    r.supports_characters && r.is_available
  )

  // Unknown service state: hold before showing anything that could dispatch.
  if (pendingStatus) {
    return (
      <div style={offlinePanelStyle} role="status">
        <p style={offlineTitleStyle}>checking image engines…</p>
        <p style={offlineBodyStyle}>Confirming a renderer is reachable before enabling generation.</p>
      </div>
    )
  }

  // A Gateway/proxy that won't answer is NOT the same as offline renderers; the
  // recovery differs (restore the Gateway vs start ComfyUI), so surface the real
  // cause instead of masking it as renderer downtime.
  if (statusFailed) {
    return (
      <div style={offlinePanelStyle} data-testid="studio-status-error">
        <p style={offlineTitleStyle}>can’t reach the image service</p>
        <p style={offlineBodyStyle}>
          The image service didn’t answer. Check that Kitty’s gateway is running, then
          check again — generation may be fine once the service is back.
        </p>
        <button
          type="button"
          onClick={() => void statusQuery.refetch()}
          disabled={statusQuery.isFetching}
          data-testid="studio-check-again"
          style={checkAgainStyle}
        >
          <RefreshCw size={13} />
          {statusQuery.isFetching ? 'checking…' : 'check again'}
        </button>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      maxWidth: 780,
      width: '100%',
      margin: '0 auto',
      padding: '24px 20px',
    }}>
      {/* Renderer-independent work (characters, plan preview) stays available
          while renderers are offline; only generation is turned off. */}
      {!enginesAvailable && (
        <div style={offlinePanelStyle} data-testid="studio-offline" role="status">
          <p style={offlineTitleStyle}>no image engine is online</p>
          <p style={offlineBodyStyle}>
            Generation is disabled until a renderer is reachable — start ComfyUI or Draw
            Things, then check again. Plan preview and characters still work.
          </p>
          <button
            type="button"
            onClick={() => void statusQuery.refetch()}
            disabled={statusQuery.isFetching}
            data-testid="studio-check-again"
            style={checkAgainStyle}
          >
            <RefreshCw size={13} />
            {statusQuery.isFetching ? 'checking…' : 'check again'}
          </button>
        </div>
      )}
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Image size={22} style={{ color: 'var(--cat-ginger)' }} />
      </div>

      {/* Prompt area */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 14,
        overflow: 'hidden',
      }}>
        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="describe what you want to create... use @ to mention a character"
          rows={3}
          style={{
            width: '100%',
            border: 'none',
            background: 'transparent',
            padding: '16px 18px 12px',
            color: 'var(--ink)',
            fontFamily: 'var(--font-body)',
            fontSize: 15,
            lineHeight: 1.6,
            resize: 'vertical',
            outline: 'none',
          }}
        />

        {/* Selected chips row */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          padding: '0 18px 8px',
          minHeight: 28,
        }}>
          {selectedChar && (
            <span style={chipStyle}>
              <User size={12} />
              {selectedChar.name}
              <button onClick={() => setSelectedChar(null)} style={chipCloseStyle} aria-label={`remove ${selectedChar.name}`}>
                <X size={10} />
              </button>
            </span>
          )}
          {routingReason && !generating && (
            <span style={routingStyle} title={routingReason}>
              {routingReason.length > 60 ? routingReason.slice(0, 57) + '…' : routingReason}
            </span>
          )}
        </div>

        {/* Controls bar */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 8,
          padding: '8px 18px 12px',
          borderTop: '1px solid var(--line)',
        }}>
          {/* Character picker */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowCharPicker(!showCharPicker)}
              style={controlBtnStyle}
              title="select character"
            >
              <User size={14} />
              {selectedChar ? selectedChar.name : 'character'}
              <ChevronDown size={12} />
            </button>
            {showCharPicker && (
              <div style={popupStyle}>
                <div style={{ padding: '4px 8px 8px', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>
                  saved characters
                </div>
                {charsLoading ? (
                  <div style={{ padding: 8, fontSize: 12, color: 'var(--ink-2)' }}>loading…</div>
                ) : characters.length === 0 ? (
                  <div style={{ padding: 8, fontSize: 12, color: 'var(--ink-2)' }}>
                    no characters yet
                  </div>
                ) : (
                  characters.map(c => (
                    <button key={c.character_id} onClick={() => { setSelectedChar(c); setShowCharPicker(false) }} style={pickerItemStyle}>
                      <User size={13} />
                      <span>{c.name}</span>
                      {c.identity_preset === 'identity_first' && <Sparkles size={11} style={{ color: 'var(--c-yellow)' }} />}
                    </button>
                  ))
                )}
                <div style={{ borderTop: '1px solid var(--line)', padding: 4 }} />
                <button onClick={() => { setShowNewChar(true); setRefQuality(null); setShowCharPicker(false) }} style={pickerItemStyle}>
                  <Plus size={13} />
                  <span>new character</span>
                </button>
              </div>
            )}
          </div>

          {/* Quality */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {(['fast', 'quality', 'maximum'] as QualityTier[]).map(t => (
              <button
                key={t}
                onClick={() => setQuality(t)}
                style={{
                  ...qualityBtnStyle,
                  background: quality === t ? 'var(--ginger-fade)' : 'transparent',
                  color: quality === t ? 'var(--cat-ginger)' : 'var(--ink-2)',
                }}
              >
                {t === 'fast' ? <Zap size={12} /> : t === 'maximum' ? <Sparkles size={12} /> : null}
                {t}
              </button>
            ))}
          </div>

          {/* Identity */}
          {selectedChar && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {(['creative', 'balanced', 'identity_first'] as IdentityMode[]).map(m => (
                <button
                  key={m}
                  onClick={() => setIdentity(m)}
                  style={{
                    ...qualityBtnStyle,
                    background: identity === m ? 'var(--ginger-fade)' : 'transparent',
                    color: identity === m ? 'var(--cat-ginger)' : 'var(--ink-2)',
                  }}
                >
                  {m === 'identity_first' ? <Shield size={12} /> : null}
                  {m.replace('_', ' ')}
                </button>
              ))}
            </div>
          )}

          <span style={{ flex: 1 }} />

          {/* Advanced toggle */}
          <button onClick={() => setShowAdvanced(!showAdvanced)} style={controlBtnStyle}>
            advanced
            <ChevronDown size={12} style={{ transform: showAdvanced ? 'rotate(180deg)' : '' }} />
          </button>

          {/* Generate / Preview / Cancel */}
          <div style={{ display: 'flex', gap: 6 }}>
            {generating && (
              <button onClick={handleCancel} style={{
                border: '1px solid var(--c-red)', borderRadius: 10,
                background: 'transparent', color: 'var(--c-red)',
                padding: '8px 14px', fontFamily: 'var(--font-body)',
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                <Square size={12} />
                cancel
              </button>
            )}
            {!generating && (
              <button
                onClick={handlePreviewPlan}
                disabled={!prompt.trim() || planPreviewing}
                style={{
                  border: '1px solid var(--line)', borderRadius: 10,
                  background: 'transparent', color: 'var(--ink)',
                  padding: '8px 14px', fontFamily: 'var(--font-body)',
                  fontSize: 14, fontWeight: 600,
                  cursor: !prompt.trim() || planPreviewing ? 'not-allowed' : 'pointer',
                  opacity: !prompt.trim() ? 0.5 : 1,
                }}
              >
                {planPreviewing ? 'previewing…' : 'preview plan'}
              </button>
            )}
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || generating || !enginesAvailable}
              title={!enginesAvailable ? 'no image engine is online' : undefined}
              style={{
                border: 'none', borderRadius: 10,
                background: generating || !enginesAvailable ? 'var(--ink-2)' : 'var(--primary)',
                color: generating || !enginesAvailable ? 'var(--bg)' : 'var(--on-primary)',
                padding: '8px 18px', fontFamily: 'var(--font-body)',
                fontSize: 14, fontWeight: 700,
                cursor: generating || !enginesAvailable ? 'not-allowed' : 'pointer',
                opacity: !prompt.trim() && !generating && enginesAvailable ? 0.5 : 1,
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {generating ? (
                <><RefreshCw size={13} className="tool-call-spin" /> generating…</>
              ) : 'generate'}
            </button>
          </div>
        </div>
      </div>

      {/* Advanced panel */}
      {showAdvanced && (
        <div style={{
          background: 'var(--surface-2)',
          border: '1px solid var(--line)',
          borderRadius: 12,
          padding: 16,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 12,
        }}>
          <AdvancedField label="seed">
            <input
              type="text"
              value={seed}
              onChange={e => setSeed(e.target.value)}
              placeholder="random"
              style={inputStyle}
            />
          </AdvancedField>
          <AdvancedField label="negative prompt">
            <input
              type="text"
              value={negativePrompt}
              onChange={e => setNegativePrompt(e.target.value)}
              placeholder="things to avoid"
              style={inputStyle}
            />
          </AdvancedField>
          {selectedChar && selectedIdentityRecipe && (
            <AdvancedField label="identity recipe">
              <span style={{ fontSize: 13, color: 'var(--ink-2)' }}>
                {selectedIdentityRecipe.display_name} (strength: {selectedIdentityRecipe.identity_strength}%)
              </span>
            </AdvancedField>
          )}
          {availableTags.length > 0 && (
            <AdvancedField label="guidance">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {availableTags.map(tag => {
                  const active = guidanceTags.includes(tag)
                  return (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => setGuidanceTags(prev =>
                        active ? prev.filter(t => t !== tag) : [...prev, tag]
                      )}
                      style={{
                        border: `1px solid ${active ? 'var(--cat-ginger)' : 'var(--line)'}`,
                        borderRadius: 999,
                        background: active ? 'var(--ginger-fade)' : 'transparent',
                        color: active ? 'var(--cat-ginger)' : 'var(--ink-2)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        padding: '3px 10px',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {tag.replace(/_/g, ' ')}
                    </button>
                  )
                })}
              </div>
            </AdvancedField>
          )}
        </div>
      )}

      {/* Plan preview */}
      {plan && (
        <PlanPreviewCard
          plan={plan}
          onDismiss={() => setPlan(null)}
          onGenerate={handleGenerate}
          enginesAvailable={enginesAvailable}
        />
      )}

      {/* Error */}
      {error && (
        <div role="alert" style={{
          padding: '10px 14px',
          borderRadius: 10,
          background: 'rgba(217, 122, 102, 0.12)',
          border: '1px solid var(--c-red)',
          color: 'var(--c-red)',
          fontSize: 13,
        }}>
          {error}
          {errorDetail && (
            <details style={{ marginTop: 6, fontSize: 11 }}>
              <summary style={{ cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>technical detail</summary>
              <pre style={{
                margin: '6px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)',
                maxHeight: 160, overflowY: 'auto',
              }}>{errorDetail}</pre>
            </details>
          )}
          <button
            onClick={() => { setError(''); setErrorDetail(null) }}
            style={{ marginLeft: 8, color: 'var(--c-red)', cursor: 'pointer', background: 'none', border: 'none' }}
          >
            dismiss
          </button>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 16,
            fontWeight: 700,
            color: 'var(--ink)',
            margin: 0,
          }}>
            recent generations
          </h2>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 10,
          }}>
            {results.slice(0, 8).map((res, i) => (
              <div key={res.job_id || i} style={{
                background: 'var(--surface)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                overflow: 'hidden',
              }}>
                <img
                  src={`/proxy/image/view/${encodeURIComponent(res.filename)}`}
                  alt={`generated image ${i + 1}`}
                  style={{
                    width: '100%',
                    aspectRatio: '1',
                    objectFit: 'cover',
                    display: 'block',
                  }}
                  loading="lazy"
                />
                <div style={{ padding: '6px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>
                  {res.routing_reason?.length ? (
                    <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {res.routing_reason.length > 40 ? res.routing_reason.slice(0, 37) + '…' : res.routing_reason}
                    </span>
                  ) : res.recipe ? (
                    <span>{res.recipe}</span>
                  ) : null}
                  {res.character_weight !== undefined && (
                    <span style={{ color: 'var(--cat-ginger)' }}>
                      identity: {Math.round(res.character_weight * 100)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* New character modal */}
      {showNewChar && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="create character"
          onClick={(e) => { if (e.target === e.currentTarget) setShowNewChar(false) }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.6)', padding: 16,
          }}
        >
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--line)',
            borderRadius: 16, padding: 20, maxWidth: 400, width: '100%',
            maxHeight: 'calc(100dvh - 32px)', overflowY: 'auto',
          }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: '0 0 14px' }}>
              new character
            </h3>
            <input
              type="text"
              value={newCharName}
              onChange={e => setNewCharName(e.target.value)}
              placeholder="character name"
              style={{
                ...inputStyle,
                width: '100%',
                marginBottom: 10,
              }}
              autoFocus
            />
            <label style={{ display: 'block', marginBottom: 10, cursor: 'pointer' }}>
              <span style={{ fontSize: 12, color: 'var(--ink-2)', display: 'block', marginBottom: 4 }}>
                reference photo (optional)
              </span>
              <div style={{
                border: '1px dashed var(--line)', borderRadius: 8, padding: '14px',
                textAlign: 'center', color: 'var(--ink-2)', fontSize: 12,
              }}>
                <Upload size={16} style={{ display: 'block', margin: '0 auto 4px' }} />
                {charRefFile ? charRefFile.name : 'click to upload'}
              </div>
              <input
                type="file"
                accept="image/*"
                onChange={e => setCharRefFile(e.target.files?.[0] ?? null)}
                style={{ display: 'none' }}
              />
            </label>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowNewChar(false)} style={cancelBtnStyle}>
                cancel
              </button>
              <button
                onClick={handleCreateCharacter}
                disabled={!newCharName.trim() || uploading}
                style={{
                  border: 'none', borderRadius: 10,
                  background: 'var(--primary)', color: 'var(--on-primary)',
                  padding: '8px 18px', fontFamily: 'var(--font-body)',
                  fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  opacity: !newCharName.trim() ? 0.5 : 1,
                }}
              >
                {uploading ? 'uploading…' : 'create'}
              </button>
            </div>
            {refQuality && (
              <div style={{
                marginTop: 12, padding: '10px 14px', borderRadius: 10,
                background: refQuality.is_perfect ? 'rgba(127, 176, 105, 0.10)' :
                  refQuality.has_blockers ? 'rgba(217, 122, 102, 0.12)' :
                  'rgba(232, 196, 106, 0.10)',
                border: `1px solid ${refQuality.is_perfect ? 'var(--c-green)' :
                  refQuality.has_blockers ? 'var(--c-red)' : 'var(--c-yellow)'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  {refQuality.is_perfect
                    ? <CheckCircle2 size={14} style={{ color: 'var(--c-green)' }} />
                    : <AlertTriangle size={14} style={{ color: refQuality.has_blockers ? 'var(--c-red)' : 'var(--c-yellow)' }} />
                  }
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>
                    {refQuality.summary}
                  </span>
                </div>
                {refQuality.dimensions && (
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>
                    {refQuality.dimensions}
                  </span>
                )}
                {refQuality.advice.map((a, i) => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 3 }}>
                    {a}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function AdvancedField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', textTransform: 'uppercase' }}>
        {label}
      </span>
      {children}
    </div>
  )
}

function PlanPreviewCard({
  plan,
  onDismiss,
  onGenerate,
  enginesAvailable = true,
}: {
  plan: Record<string, unknown>
  onDismiss: () => void
  onGenerate: () => void
  enginesAvailable?: boolean
}) {
  const refs = Array.isArray(plan.references)
    ? plan.references.filter(
        (ref): ref is { name?: string; reason?: string; path?: string } =>
          typeof ref === 'object' && ref !== null,
      )
    : []
  const tags = Array.isArray(plan.guidance_tags)
    ? plan.guidance_tags.filter((tag): tag is string => typeof tag === 'string')
    : []
  const recipeId = typeof plan.recipe_id === 'string' ? plan.recipe_id : null
  const characterRefPath = typeof plan.character_ref_path === 'string'
    ? plan.character_ref_path
    : null

  return (
    <section style={{
      background: 'var(--surface)',
      border: '1px solid var(--c-green)',
      borderRadius: 14,
      padding: 20,
      display: 'grid',
      gap: 16,
    }} aria-label="Generation plan preview">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <h2 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 18,
          fontWeight: 700,
          color: 'var(--ink)',
          margin: 0,
        }}>
          plan preview
        </h2>
        <button onClick={onDismiss} style={{
          border: '1px solid var(--line)', borderRadius: 8,
          background: 'transparent', color: 'var(--ink-2)',
          padding: '4px 10px', fontFamily: 'var(--font-body)',
          fontSize: 12, cursor: 'pointer',
        }}>
          dismiss
        </button>
      </div>

      {/* Refined prompt */}
      <div style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', textTransform: 'uppercase' }}>
          prompt
        </span>
        <p style={{
          margin: 0,
          fontFamily: 'var(--font-body)',
          fontSize: 14,
          color: 'var(--ink)',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
        }}>
          {String(plan.refined_prompt ?? plan.original_prompt ?? '')}
        </p>
      </div>

      {/* Resolved references */}
      {refs.length > 0 && (
        <div style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', textTransform: 'uppercase' }}>
            references
          </span>
          {refs.map((ref, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 10px',
              background: 'var(--surface-2)',
              borderRadius: 8,
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>
                {ref.name}
              </span>
              <span style={{ fontSize: 11, color: 'var(--ink-2)' }}>
                {ref.reason}
              </span>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', marginLeft: 'auto' }}>
                {ref.path?.split('/').pop()}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Guidance tags */}
      {tags.length > 0 && (
        <div style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', textTransform: 'uppercase' }}>
            guidance
          </span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {tags.map((tag) => (
              <span key={tag} style={{
                padding: '3px 10px',
                background: 'var(--ginger-fade)',
                borderRadius: 999,
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                color: 'var(--cat-ginger)',
              }}>
                {tag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recipe + character ref */}
      {(Boolean(recipeId) || Boolean(characterRefPath)) && (
        <div style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', textTransform: 'uppercase' }}>
            resolved
          </span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {recipeId && (
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>
                recipe: {recipeId}
              </span>
            )}
            {characterRefPath && (
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)' }}>
                ref: {characterRefPath.split('/').slice(-2).join('/')}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Created at */}
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--ink-2)', opacity: 0.6 }}>
        plan created {new Date(String(plan.created_at)).toLocaleString()}
      </span>

      {/* Approve & generate */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={onGenerate}
          disabled={!enginesAvailable}
          title={enginesAvailable ? undefined : 'no image engine is online'}
          style={{
            border: 'none', borderRadius: 10,
            background: enginesAvailable ? 'var(--primary)' : 'var(--ink-2)',
            color: enginesAvailable ? 'var(--on-primary)' : 'var(--bg)',
            padding: '8px 18px', fontFamily: 'var(--font-body)',
            fontSize: 14, fontWeight: 700, cursor: enginesAvailable ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          approve & generate
        </button>
      </div>
    </section>
  )
}

const chipStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  padding: '3px 10px', borderRadius: 999,
  background: 'var(--ginger-fade)', color: 'var(--cat-ginger)',
  fontSize: 12, fontWeight: 500, fontFamily: 'var(--font-body)',
}

const chipCloseStyle: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'inherit', padding: 0, display: 'flex',
}

const routingStyle: React.CSSProperties = {
  fontSize: 11, fontFamily: 'var(--font-mono)',
  color: 'var(--ink-2)', padding: '3px 8px',
  borderRadius: 6, background: 'var(--surface-2)',
  maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
}

const controlBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  padding: '5px 10px', borderRadius: 8,
  border: '1px solid var(--line)', background: 'transparent',
  color: 'var(--ink-2)', fontFamily: 'var(--font-body)',
  fontSize: 12, cursor: 'pointer',
}

const qualityBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '4px 10px', borderRadius: 8,
  border: 'none', fontFamily: 'var(--font-body)',
  fontSize: 12, fontWeight: 500, cursor: 'pointer',
}

const popupStyle: React.CSSProperties = {
  position: 'absolute', top: '100%', left: 0, marginTop: 4,
  background: 'var(--surface)', border: '1px solid var(--line)',
  borderRadius: 12, minWidth: 220, maxWidth: 'calc(100vw - 40px)',
  maxHeight: 'min(60dvh, 360px)', overflowY: 'auto',
  zIndex: 100, boxShadow: 'var(--shadow)', overflowX: 'hidden',
}

const pickerItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  width: '100%', padding: '8px 12px',
  border: 'none', background: 'transparent',
  cursor: 'pointer', color: 'var(--ink)',
  fontFamily: 'var(--font-body)', fontSize: 13,
}

const inputStyle: React.CSSProperties = {
  border: '1px solid var(--line)', borderRadius: 8,
  padding: '7px 10px', background: 'var(--surface)',
  color: 'var(--ink)', fontFamily: 'var(--font-mono)',
  fontSize: 12, outline: 'none',
}

const cancelBtnStyle: React.CSSProperties = {
  border: '1px solid var(--line)', borderRadius: 10, background: 'transparent',
  color: 'var(--ink-2)', padding: '8px 16px', fontFamily: 'var(--font-body)',
  fontSize: 14, fontWeight: 500, cursor: 'pointer',
}

const offlinePanelStyle: React.CSSProperties = {
  maxWidth: 780, width: '100%', margin: '0 auto',
  padding: '20px', display: 'grid', gap: 8, alignContent: 'start',
  background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 12,
}

const offlineTitleStyle: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color: 'var(--ink)',
}

const offlineBodyStyle: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.6,
}

const checkAgainStyle: React.CSSProperties = {
  alignSelf: 'flex-start', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600,
  padding: '8px 16px', borderRadius: 10, border: 'none', cursor: 'pointer', color: 'var(--on-primary)',
  background: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: 6,
}

/** Studio operation whose catch path formats an HTML/JSON error. */
type StudioErrorOp = 'generate' | 'plan' | 'character'

// Recovery text must name the failing subsystem, not a renderer. Generation
// legitimately points at the renderer, but plan preview and character creation
// never contact one, so an HTML 500 from those must not imply renderer downtime
// (PR #355 finding 6).
const STUDIO_ERROR_MESSAGES: Record<StudioErrorOp, string> = {
  generate: 'the image service hit an internal error — check your renderer and try again',
  plan: 'the planning service hit an internal error — check that the image service is running and try again',
  character: 'the character service hit an internal error — check that the image service is running and try again',
}

/** Turn a possible raw backend error (JSON {detail}, HTML error page) into a
 *  human message plus an optional technical detail the user can expand. */
function friendlyStudioError(err: unknown, op: StudioErrorOp = 'generate'): { message: string; detail: string | null } {
  const raw = err instanceof Error ? err.message : 'generation failed'
  const trimmed = raw.trim()
  // Standard proxy/framework error pages commonly start with "<!DOCTYPE html>",
  // not "<html>"; detect any HTML document and keep its body in the expandable
  // technical detail rather than rendering it as the primary message.
  if (
    /^<!doctype html/i.test(trimmed)
    || /^<html/i.test(trimmed)
    || /internal server error/i.test(trimmed)
  ) {
    return {
      message: STUDIO_ERROR_MESSAGES[op],
      detail: trimmed.slice(0, 2000),
    }
  }
  try {
    const parsed = JSON.parse(trimmed)
    if (parsed && typeof parsed.detail === 'string') {
      return { message: parsed.detail, detail: raw !== parsed.detail ? raw : null }
    }
  } catch { /* not JSON → raw message */ }
  return { message: trimmed, detail: null }
}
