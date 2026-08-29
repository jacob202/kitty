'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { AlertTriangle, CheckCircle2, Image as ImageIcon, Plus, RefreshCw, Square, Upload, User, X } from 'lucide-react'
import { useImageStatus } from '@/lib/queries'

type QualityTier = 'fast' | 'quality' | 'maximum'
type IdentityMode = 'creative' | 'balanced' | 'identity_first'
type OutputCount = 1 | 2 | 4

type EstimateFact = {
  state: 'known' | 'unknown'
  usd?: number | null
  seconds?: number | null
  basis?: string | null
  samples?: number
}

type EstimatePayload = {
  provider: string
  model_id: string | null
  recipe_id: string
  routing_reason: string
  count: OutputCount
  per_image_estimate: { cost: EstimateFact; duration: EstimateFact }
  estimate: { cost: EstimateFact; duration: EstimateFact }
}

type BatchItem = {
  item_id: string
  ordinal: number
  status: string
  job_id: string | null
  result: { job_id?: string; filename?: string; routing_reason?: string } | null
  error: string | null
}

type ImageBatch = {
  batch_id: string
  session_id?: string | null
  status: string
  count: number
  estimate: { cost?: EstimateFact; duration?: EstimateFact }
  request?: { prompt?: string }
  items: BatchItem[]
}

type AgentDecision = {
  action: 'generate' | 'edit' | 'cancel' | 'clarify'
  session_id: string
  summary: string
  plan_id: string | null
  protected_traits?: string[]
  requested_changes?: string[]
  question?: string | null
  reason?: string | null
}

type Turn = {
  id: string
  role: 'user' | 'assistant'
  text: string
  protectedTraits?: string[]
  requestedChanges?: string[]
}

type CharacterRef = {
  ref_id: string
  is_primary: boolean
  original_name: string | null
  storage_path: string
}

type StudioCharacter = {
  character_id: string
  name: string
  description: string | null
  identity_preset: string
  references: CharacterRef[]
}

type RefQuality = {
  has_blockers: boolean
  has_warnings: boolean
  is_perfect: boolean
  summary: string
  advice: string[]
  dimensions: string | null
}

const SESSION_KEY = 'kitty-image-lab-session'
let turnSequence = 0

function turnId(): string {
  turnSequence += 1
  return `image-lab-turn-${turnSequence}`
}

function humanError(error: unknown): string {
  if (error instanceof Error) {
    const text = error.message
    if (/<!doctype|<html/i.test(text)) return 'Image Lab hit an internal error. Technical details are available in the service logs.'
    return text.replace(/^\s*\{"detail":\s*"?/, '').replace(/"?\}\s*$/, '')
  }
  return 'Image Lab could not complete that request.'
}

function money(value: number): string {
  return `$${value.toFixed(2)}`
}

function duration(seconds: number): string {
  if (seconds < 90) return `~${Math.round(seconds)} sec`
  return `~${Math.max(1, Math.round(seconds / 60))} min`
}

async function jsonOrError(response: Response): Promise<any> {
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `request failed (${response.status})`)
  }
  return await response.json()
}

function useStudioCharacters() {
  const [characters, setCharacters] = useState<StudioCharacter[]>([])
  const [loading, setLoading] = useState(true)

  const fetchCharacters = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/proxy/studio/characters')
      if (response.ok) {
        const payload = await response.json()
        const normalized = (payload.characters ?? []).map((character: StudioCharacter) => ({
          ...character, references: character.references ?? [],
        }))
        setCharacters(normalized)
      }
    } catch {
      // Character listing is optional; the workspace works without it.
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchCharacters() }, [fetchCharacters])

  const createCharacter = useCallback(async (name: string) => {
    const response = await fetch('/proxy/studio/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!response.ok) throw new Error(await response.text())
    const raw = await response.json() as StudioCharacter
    const character = { ...raw, references: raw.references ?? [] }
    setCharacters(previous => [character, ...previous])
    return character
  }, [])

  const uploadReference = useCallback(async (characterId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`/proxy/studio/characters/${characterId}/references`, {
      method: 'POST',
      body: form,
    })
    if (!response.ok) throw new Error(await response.text())
    return await response.json() as { quality?: RefQuality }
  }, [])

  return { characters, loading, fetchCharacters, createCharacter, uploadReference }
}

export function ImageLab({ compact = false }: { compact?: boolean } = {}) {
  const status = useImageStatus()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [quality, setQuality] = useState<QualityTier>('quality')
  const [identity, setIdentity] = useState<IdentityMode>('balanced')
  const [count, setCount] = useState<OutputCount>(1)
  const [estimate, setEstimate] = useState<EstimatePayload | null>(null)
  const [estimateLoading, setEstimateLoading] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [batches, setBatches] = useState<ImageBatch[]>([])
  const [anchorJobId, setAnchorJobId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const estimateAbort = useRef<AbortController | null>(null)

  const { characters, loading: charactersLoading, createCharacter, uploadReference } = useStudioCharacters()
  const [selectedCharacter, setSelectedCharacter] = useState<StudioCharacter | null>(null)
  const [boundCharacterId, setBoundCharacterId] = useState<string | null>(null)
  const [showCharPicker, setShowCharPicker] = useState(false)
  const [newCharName, setNewCharName] = useState('')
  const [charRefFile, setCharRefFile] = useState<File | null>(null)
  const [charUploading, setCharUploading] = useState(false)
  const [refQuality, setRefQuality] = useState<RefQuality | null>(null)

  const enginesAvailable = status.data?.available === true
    || (status.data?.engines ?? []).some(engine => engine.available)
  // "no engine is online" on its own leaves the user with nothing to do. The
  // gateway already knows why each engine is down; carry that through instead
  // of dropping it.
  const offlineReasons = useMemo(
    () => (status.data?.engines ?? [])
      .filter(engine => !engine.available && engine.unavailable_reason)
      .filter(engine => !/\bKITTY_[A-Z0-9_]+\b|\.env\b/i.test(engine.unavailable_reason as string))
      .map(engine => ({ name: engine.name, label: engine.label, reason: engine.unavailable_reason as string })),
    [status.data?.engines],
  )
  const activeBatches = useMemo(
    () => batches.filter(batch => batch.status === 'queued' || batch.status === 'running'),
    [batches],
  )

  const appendTurn = useCallback((turn: Omit<Turn, 'id'>) => {
    setTurns(previous => [...previous, { ...turn, id: turnId() }])
  }, [])

  const refreshBatch = useCallback(async (batchId: string) => {
    try {
      const response = await fetch(`/proxy/studio/batches/${batchId}`)
      const updated = await jsonOrError(response) as ImageBatch
      setBatches(previous => {
        const index = previous.findIndex(batch => batch.batch_id === batchId)
        if (index < 0) return [updated, ...previous]
        const copy = [...previous]
        copy[index] = updated
        return copy
      })
    } catch {
      // A transient poll failure does not erase durable queue state.
    }
  }, [])

  useEffect(() => {
    const stored = window.localStorage.getItem(SESSION_KEY)
    if (!stored) return
    let cancelled = false
    void (async () => {
      try {
        const sessionResponse = await fetch(`/proxy/studio/sessions/${encodeURIComponent(stored)}`)
        if (sessionResponse.status === 404) {
          window.localStorage.removeItem(SESSION_KEY)
          if (!cancelled) setSessionId(null)
          return
        }
        const session = await jsonOrError(sessionResponse)
        if (cancelled) return
        setSessionId(session.session_id)
        setAnchorJobId(session.anchor_job_id ?? null)
        setBoundCharacterId(typeof session.character_id === 'string' ? session.character_id : null)
        const restoredTurns = Array.isArray(session.turns)
          ? session.turns
              .filter((turn: any) => (turn.role === 'user' || turn.role === 'assistant') && typeof turn.content === 'string')
              .map((turn: any) => ({ id: turnId(), role: turn.role, text: turn.content }))
          : []
        if (restoredTurns.length) setTurns(restoredTurns)
        const batchesResponse = await fetch(`/proxy/studio/batches?session_id=${encodeURIComponent(stored)}`)
        const batchPayload = await jsonOrError(batchesResponse)
        if (!cancelled && Array.isArray(batchPayload.batches)) setBatches(batchPayload.batches)
      } catch {
        if (!cancelled) setSessionId(null)
      }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (charactersLoading || !boundCharacterId) return
    const match = characters.find(character => character.character_id === boundCharacterId)
    if (match && match.character_id !== selectedCharacter?.character_id) setSelectedCharacter(match)
  }, [characters, charactersLoading, boundCharacterId, selectedCharacter?.character_id])

  useEffect(() => {
    estimateAbort.current?.abort()
    const controller = new AbortController()
    estimateAbort.current = controller
    setEstimateLoading(true)
    void fetch('/proxy/studio/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quality, identity, count, character_id: boundCharacterId ?? selectedCharacter?.character_id ?? undefined }),
      signal: controller.signal,
    })
      .then(jsonOrError)
      .then(payload => {
        if (!controller.signal.aborted) setEstimate(payload as EstimatePayload)
      })
      .catch(error => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) setEstimate(null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setEstimateLoading(false)
      })
    return () => controller.abort()
  }, [quality, identity, count, boundCharacterId, selectedCharacter?.character_id])

  useEffect(() => {
    if (activeBatches.length === 0) return
    const timer = window.setInterval(() => {
      for (const batch of activeBatches) void refreshBatch(batch.batch_id)
    }, 1500)
    return () => window.clearInterval(timer)
  }, [activeBatches, refreshBatch])

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId
    const response = await fetch('/proxy/studio/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(selectedCharacter ? { character_id: selectedCharacter.character_id } : {}),
    })
    const session = await jsonOrError(response)
    const id = String(session.session_id)
    setSessionId(id)
    setBoundCharacterId(selectedCharacter?.character_id ?? null)
    window.localStorage.setItem(SESSION_KEY, id)
    return id
  }

  async function bindCharacter(character: StudioCharacter) {
    setSelectedCharacter(character)
    setShowCharPicker(false)
    if (!sessionId) {
      setBoundCharacterId(character.character_id)
      return
    }
    try {
      await jsonOrError(await fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character_id: character.character_id }),
      }))
      setBoundCharacterId(character.character_id)
    } catch (err) {
      setError(humanError(err))
    }
  }

  async function clearCharacter() {
    const clearId = selectedCharacter?.character_id ?? null
    setSelectedCharacter(null)
    setBoundCharacterId(null)
    if (!sessionId || !clearId) return
    try {
      await jsonOrError(await fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clear_character: true }),
      }))
    } catch (err) {
      setError(humanError(err))
    }
  }

  async function createNewCharacter() {
    const name = newCharName.trim()
    if (!name || charUploading) return
    setCharUploading(true)
    setError(null)
    try {
      const character = await createCharacter(name)
      if (charRefFile) {
        const refResult = await uploadReference(character.character_id, charRefFile)
        setRefQuality(refResult.quality ?? null)
      } else {
        setRefQuality(null)
      }
      setNewCharName('')
      setCharRefFile(null)
      setShowCharPicker(false)
      await bindCharacter(character)
    } catch (err) {
      setError(humanError(err))
    } finally {
      setCharUploading(false)
    }
  }

  async function send() {
    const text = prompt.trim()
    if (!text || busy || !enginesAvailable) return
    setBusy(true)
    setError(null)
    appendTurn({ role: 'user', text })
    setPrompt('')
    try {
      const activeSession = await ensureSession()
      const decision = await jsonOrError(await fetch('/proxy/studio/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSession, request: text }),
      })) as AgentDecision

      if (decision.action === 'clarify' || decision.action === 'cancel' || !decision.plan_id) {
        appendTurn({ role: 'assistant', text: decision.question || decision.reason || decision.summary })
        return
      }

      appendTurn({
        role: 'assistant',
        text: decision.summary,
        protectedTraits: decision.protected_traits ?? [],
        requestedChanges: decision.requested_changes ?? [],
      })

      const batch = await jsonOrError(await fetch('/proxy/studio/batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          plan_id: decision.plan_id,
          session_id: activeSession,
          quality,
          identity,
          character_id: boundCharacterId ?? selectedCharacter?.character_id ?? undefined,
          count,
        }),
      })) as ImageBatch
      setBatches(previous => [batch, ...previous.filter(item => item.batch_id !== batch.batch_id)])
    } catch (err) {
      setError(humanError(err))
    } finally {
      setBusy(false)
    }
  }

  async function cancelBatch(batchId: string) {
    try {
      const updated = await jsonOrError(await fetch(`/proxy/studio/batches/${batchId}/cancel`, { method: 'POST' })) as ImageBatch
      setBatches(previous => previous.map(batch => batch.batch_id === batchId ? updated : batch))
    } catch (err) {
      setError(humanError(err))
    }
  }

  async function useThis(jobId: string) {
    if (!sessionId) return
    try {
      const session = await jsonOrError(await fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}/anchor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId }),
      }))
      setAnchorJobId(session.anchor_job_id ?? jobId)
    } catch (err) {
      setError(humanError(err))
    }
  }

  async function clearAnchor() {
    if (!sessionId) return
    try {
      const session = await jsonOrError(await fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}/anchor`, {
        method: 'DELETE',
      }))
      setAnchorJobId(session.anchor_job_id ?? null)
    } catch (err) {
      setError(humanError(err))
    }
  }

  const estimateText = (() => {
    if (estimateLoading) return 'estimating…'
    if (!estimate) return `${count} image${count === 1 ? '' : 's'} · cost/time not known yet`
    const parts = [`${count} image${count === 1 ? '' : 's'}`]
    const cost = estimate.estimate.cost
    const time = estimate.estimate.duration
    parts.push(cost.state === 'known' && typeof cost.usd === 'number' ? `estimated ${money(cost.usd)}` : 'cost unknown')
    parts.push(time.state === 'known' && typeof time.seconds === 'number' ? duration(time.seconds) : 'time unknown')
    return parts.join(' · ')
  })()

  const completedCount = batches.reduce(
    (total, batch) => total + batch.items.filter(item => item.status === 'succeeded' && item.result?.filename).length,
    0,
  )

  return (
    <section style={shellStyle} aria-label="Image Lab">
      <header style={{ ...headerStyle, ...(compact ? { flexDirection: 'column' } : {}) }}>
        <div>
          <h1 style={{ ...titleStyle, fontSize: compact ? 28 : 32 }}>Image Lab</h1>
          <p style={subtitleStyle}>
            Create with references, iterate in one session, and keep every real result in one workspace.
          </p>
        </div>
        <div
          role="status"
          aria-label="Image generation availability"
          style={{
            ...readinessStyle,
            color: status.isPending
              ? 'var(--color-text-secondary)'
              : enginesAvailable
                ? 'var(--color-success)'
                : 'var(--color-destructive)',
          }}
        >
          <span
            aria-hidden="true"
            style={{
              ...dotStyle,
              background: status.isPending
                ? 'var(--color-text-muted)'
                : enginesAvailable
                  ? 'var(--color-success)'
                  : 'var(--color-destructive)',
            }}
          />
          {status.isPending
            ? 'Checking generation…'
            : status.isError
              ? 'Image service unavailable'
              : enginesAvailable
                ? 'Ready to generate'
                : 'Generation unavailable'}
        </div>
      </header>

      {status.isError && (
        <div role="alert" style={noticeStyle}>
          <div style={noticeBodyStyle}>
            <strong style={noticeTitleStyle}>Image service is unavailable</strong>
            <span>Nothing will be dispatched until Kitty can reach the image service.</span>
          </div>
          <button type="button" onClick={() => void status.refetch()} style={secondaryButtonStyle}>Check again</button>
        </div>
      )}
      {!status.isError && !status.isPending && !enginesAvailable && (
        <div role="status" style={noticeStyle}>
          <div style={noticeBodyStyle}>
            <strong style={noticeTitleStyle}>Generation is unavailable right now</strong>
            <span>No image engine is online. Your session and references remain available, but Generate stays disabled.</span>
            {offlineReasons.length > 0 && (
              <ul style={reasonListStyle}>
                {offlineReasons.map(engine => (
                  <li key={engine.name}>
                    <strong>{engine.label}:</strong> {engine.reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button type="button" onClick={() => void status.refetch()} style={secondaryButtonStyle}>Check again</button>
        </div>
      )}

      <details data-testid="image-lab-runtime-details" style={detailsStyle}>
        <summary style={detailsSummaryStyle}>Generation details</summary>
        <div style={detailsBodyStyle}>
          <span>Service: {status.isError ? 'unreachable' : enginesAvailable ? 'available' : status.isPending ? 'checking' : 'unavailable'}</span>
          <span data-testid="image-lab-estimate-details">Estimate: {estimateText}</span>
          {estimate && (
            <span>
              Route: {estimate.provider}{estimate.model_id ? ` · ${estimate.model_id}` : ''} · {estimate.routing_reason}
            </span>
          )}
          <span>Session: {sessionId ? 'active and restorable' : 'starts with your first generation request'}</span>
          {anchorJobId && <span>Selected source job: {anchorJobId}</span>}
        </div>
      </details>

      <div
        data-testid="image-lab-workspace"
        style={{ ...workspaceStyle, ...(compact ? { gridTemplateColumns: '1fr' } : {}) }}
      >
        <div style={setupColumnStyle}>
          <section
            data-testid="image-lab-references"
            aria-label="References"
            style={sectionStyle}
          >
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>References</h2>
                <p style={sectionDescriptionStyle}>Bind the identity or source image Kitty should preserve in this session.</p>
              </div>
            </div>

            <div style={referenceStackStyle}>
              {selectedCharacter ? (
                <div data-testid="image-lab-character" style={boundReferenceStyle}>
                  <div style={referenceIdentityStyle}>
                    <span style={referenceIconStyle}><User size={18} /></span>
                    <div style={{ minWidth: 0 }}>
                      <strong style={referenceNameStyle}>{selectedCharacter.name}</strong>
                      <div style={supportingTextStyle}>
                        {selectedCharacter.references.length > 0
                          ? `${selectedCharacter.references.length} reference${selectedCharacter.references.length === 1 ? '' : 's'} bound`
                          : <span>no ref · add a reference photo when you recreate or update this character</span>}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    aria-label="clear reference character"
                    onClick={() => void clearCharacter()}
                    style={quietIconButtonStyle}
                  >
                    <X size={17} />
                  </button>
                </div>
              ) : (
                <div style={referenceEmptyStyle}>
                  <User size={20} />
                  <div>
                    <strong style={referenceNameStyle}>No character bound</strong>
                    <div style={supportingTextStyle}>You can generate without one, or bind a saved character for identity continuity.</div>
                  </div>
                </div>
              )}

              <div style={charControlStyle}>
                <button
                  type="button"
                  data-testid="image-lab-character-picker"
                  aria-expanded={showCharPicker}
                  onClick={() => setShowCharPicker(open => !open)}
                  style={characterButtonStyle}
                >
                  {selectedCharacter ? <User size={17} /> : <Plus size={17} />}
                  {selectedCharacter ? 'Change character' : 'Choose or create character'}
                </button>

                {showCharPicker && (
                  <div style={pickerPanelStyle}>
                    <div style={pickerSectionLabelStyle}>Saved characters</div>
                    {charactersLoading ? (
                      <div style={pickerEmptyStyle}>Loading saved characters…</div>
                    ) : characters.length === 0 ? (
                      <div style={pickerEmptyStyle}>No saved characters yet. Create the first one below.</div>
                    ) : (
                      <div style={pickerListStyle}>
                        {characters.map(character => (
                          <button
                            key={character.character_id}
                            type="button"
                            onClick={() => void bindCharacter(character)}
                            style={pickerItemStyle}
                          >
                            <span style={referenceIconStyle}><User size={16} /></span>
                            <span style={{ minWidth: 0, flex: 1, overflowWrap: 'anywhere' }}>{character.name}</span>
                            <span style={pickerMetaStyle}>
                              {character.references.length === 0
                                ? 'no ref'
                                : `${character.references.length} ref${character.references.length === 1 ? '' : 's'}`}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}

                    <div style={pickerDividerStyle} />
                    <div style={pickerSectionLabelStyle}>Create character</div>
                    <div style={popupFormStyle}>
                      <input
                        type="text"
                        value={newCharName}
                        onChange={event => setNewCharName(event.target.value)}
                        onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void createNewCharacter() } }}
                        placeholder="new character name"
                        aria-label="New character name"
                        style={inputStyle}
                      />
                      <label style={fileLabelStyle}>
                        <Upload size={16} />
                        <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>{charRefFile ? charRefFile.name : 'Add reference photo (optional)'}</span>
                        <input type="file" accept="image/*" onChange={event => setCharRefFile(event.target.files?.[0] ?? null)} style={{ display: 'none' }} />
                      </label>
                      <button
                        type="button"
                        data-testid="image-lab-create-character"
                        disabled={!newCharName.trim() || charUploading}
                        onClick={() => void createNewCharacter()}
                        style={{ ...secondaryButtonStyle, alignSelf: 'flex-start', opacity: !newCharName.trim() || charUploading ? 0.55 : 1 }}
                      >
                        {charUploading ? 'Creating…' : 'Create and bind'}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {anchorJobId && (
                <div data-testid="image-lab-anchor" style={anchorStyle}>
                  <div>
                    <strong style={referenceNameStyle}>Selected result is the edit source</strong>
                    <div style={supportingTextStyle}>Your next change will build from this real artifact.</div>
                  </div>
                  <button type="button" aria-label="clear selected image" onClick={() => void clearAnchor()} style={quietIconButtonStyle}>
                    <X size={17} />
                  </button>
                </div>
              )}

              {refQuality && (
                <div style={qualityBannerStyle(refQuality)}>
                  <div style={qualityBannerTitleStyle}>
                    {refQuality.is_perfect
                      ? <CheckCircle2 size={16} style={{ color: 'var(--color-success)' }} />
                      : <AlertTriangle size={16} style={{ color: refQuality.has_blockers ? 'var(--color-destructive)' : 'var(--color-warning)' }} />}
                    <span>{refQuality.summary}</span>
                  </div>
                  {refQuality.dimensions && <span style={supportingTextStyle}>{refQuality.dimensions}</span>}
                  {refQuality.advice.map((advice, index) => (
                    <div key={index} style={qualityAdviceStyle}>{advice}</div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section
            data-testid="image-lab-create"
            aria-label="Create"
            style={sectionStyle}
          >
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>Create</h2>
                <p style={sectionDescriptionStyle}>Describe the scene or change. Kitty turns it into the generation plan.</p>
              </div>
            </div>

            <div style={conversationStyle} aria-label="Image planning conversation">
              {turns.length === 0 ? (
                <div style={conversationEmptyStyle}>Start with the image you want, or describe what should change from the selected result.</div>
              ) : turns.map(turn => (
                <div key={turn.id} style={{ ...turnStyle, alignSelf: turn.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <strong style={turnRoleStyle}>{turn.role === 'user' ? 'You' : 'Kitty'}</strong>
                  <span>{turn.text}</span>
                  {turn.protectedTraits && turn.protectedTraits.length > 0 && (
                    <span style={turnMetaStyle}>Keep fixed: {turn.protectedTraits.join(', ')}</span>
                  )}
                  {turn.requestedChanges && turn.requestedChanges.length > 0 && (
                    <span style={turnMetaStyle}>Change: {turn.requestedChanges.join(', ')}</span>
                  )}
                </div>
              ))}
            </div>

            <div style={composerStyle}>
              <textarea
                value={prompt}
                onChange={event => setPrompt(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void send()
                  }
                }}
                placeholder="tell Kitty what you want to make or change…"
                rows={compact ? 4 : 5}
                style={textareaStyle}
              />

              <div style={controlsStyle}>
                <div aria-label="image count" style={segmentedStyle}>
                  {([1, 2, 4] as OutputCount[]).map(value => (
                    <button
                      key={value}
                      type="button"
                      aria-label={`${value} image${value === 1 ? '' : 's'}`}
                      onClick={() => setCount(value)}
                      style={{ ...segmentButtonStyle, ...(count === value ? selectedSegmentStyle : {}) }}
                    >{value}</button>
                  ))}
                </div>
                <select aria-label="quality" value={quality} onChange={event => setQuality(event.target.value as QualityTier)} style={selectStyle}>
                  <option value="fast">Fast</option>
                  <option value="quality">Quality</option>
                  <option value="maximum">Maximum</option>
                </select>
                <select aria-label="identity" value={identity} onChange={event => setIdentity(event.target.value as IdentityMode)} style={selectStyle}>
                  <option value="creative">Creative</option>
                  <option value="balanced">Balanced</option>
                  <option value="identity_first">Identity first</option>
                </select>
              </div>

              <div style={{ ...actionRowStyle, ...(compact ? { alignItems: 'stretch' } : {}) }}>
                <span data-testid="image-lab-estimate" style={estimateStyle}>{estimateText}</span>
                <button
                  type="button"
                  data-testid="image-lab-send"
                  disabled={!enginesAvailable || busy || !prompt.trim()}
                  onClick={() => void send()}
                  style={{
                    ...sendButtonStyle,
                    ...(compact ? { width: '100%', justifyContent: 'center' } : {}),
                    opacity: !enginesAvailable || busy || !prompt.trim() ? 0.55 : 1,
                    cursor: !enginesAvailable || busy || !prompt.trim() ? 'not-allowed' : 'pointer',
                  }}
                >
                  {busy ? <RefreshCw size={18} /> : <ImageIcon size={18} />}
                  {busy ? 'Planning…' : enginesAvailable ? 'Generate' : 'Generation unavailable'}
                </button>
              </div>
            </div>
            {error && <div role="alert" style={errorStyle}>{error}</div>}
          </section>
        </div>

        <div style={outputColumnStyle}>
          <section
            data-testid="image-lab-results"
            aria-label="Results"
            style={resultsSectionStyle}
          >
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>Results</h2>
                <p style={sectionDescriptionStyle}>Completed images stay large and usable; in-progress items keep their real state.</p>
              </div>
              <span style={countStyle}>{completedCount} complete</span>
            </div>

            {batches.length === 0 ? (
              <div style={resultsEmptyStyle}>
                <ImageIcon size={24} />
                <strong style={referenceNameStyle}>Your images will appear here</strong>
                <span style={supportingTextStyle}>Nothing is queued yet. Set references, describe the image, then Generate.</span>
              </div>
            ) : (
              <div style={batchResultsStackStyle}>
                {batches.map(batch => (
                  <article key={batch.batch_id} style={resultBatchStyle}>
                    <div style={resultBatchHeaderStyle}>
                      <strong style={{ overflowWrap: 'anywhere' }}>{batch.request?.prompt || 'Image generation'}</strong>
                      <span style={statusBadgeStyle}>{batch.status}</span>
                    </div>
                    <div style={{ ...resultGridStyle, ...(compact ? { gridTemplateColumns: '1fr' } : {}) }}>
                      {batch.items.map(item => (
                        <div key={item.item_id} style={resultCardStyle}>
                          {item.status === 'succeeded' && item.result?.filename ? (
                            <>
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={`/proxy/image/view/${encodeURIComponent(item.result.filename)}`}
                                alt={`Generated image ${item.ordinal + 1}`}
                                style={imageStyle}
                              />
                              {item.job_id && (
                                <button type="button" onClick={() => void useThis(item.job_id as string)} style={secondaryButtonStyle}>
                                  Use as edit source
                                </button>
                              )}
                            </>
                          ) : (
                            <div style={placeholderStyle}>
                              {item.status === 'running' ? (
                                <><RefreshCw size={20} /><strong>Generating image…</strong><span>Kitty is waiting for the real artifact.</span></>
                              ) : item.status === 'failed' ? (
                                <><AlertTriangle size={20} /><strong>Generation failed</strong><span>{item.error || 'No error detail was returned.'}</span><span>Adjust the request above and generate again.</span></>
                              ) : item.status === 'cancelled' || item.status === 'canceled' ? (
                                <><Square size={20} /><strong>Cancelled</strong><span>This item was not generated.</span></>
                              ) : (
                                <><RefreshCw size={20} /><strong>Waiting to start</strong><span>Queued in Image Lab.</span></>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section
            data-testid="image-lab-activity"
            aria-label="Activity"
            style={sectionStyle}
          >
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>Activity</h2>
                <p style={sectionDescriptionStyle}>Real queue state for this session, with cancellation available while work is active.</p>
              </div>
              <span style={countStyle}>{batches.length} batch{batches.length === 1 ? '' : 'es'}</span>
            </div>

            {batches.length === 0 ? (
              <div style={activityEmptyStyle}>No generation activity yet.</div>
            ) : (
              <div style={activityListStyle} aria-live="polite">
                {batches.map(batch => {
                  const firstFailure = batch.items.find(item => item.status === 'failed')?.error
                  return (
                    <div key={batch.batch_id} style={activityRowStyle}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <strong style={activityTitleStyle}>
                          {batch.count} image{batch.count === 1 ? '' : 's'} {batch.status}
                        </strong>
                        <div style={supportingTextStyle}>{batch.request?.prompt || 'Image generation'}</div>
                        {firstFailure && <div style={failureTextStyle}>{firstFailure}</div>}
                      </div>
                      {(batch.status === 'queued' || batch.status === 'running') && (
                        <button type="button" onClick={() => void cancelBatch(batch.batch_id)} style={secondaryButtonStyle}>
                          <Square size={15} /> Cancel
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </section>
  )
}

const shellStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 'var(--s-4)', width: '100%', minHeight: '100%', minWidth: 0,
}
const headerStyle: CSSProperties = {
  display: 'flex', justifyContent: 'space-between', gap: 'var(--s-4)', alignItems: 'flex-start', minWidth: 0,
}
const titleStyle: CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)', lineHeight: 1.12,
}
const subtitleStyle: CSSProperties = {
  margin: '6px 0 0', fontSize: 15, lineHeight: 1.55, color: 'var(--color-text-secondary)', maxWidth: 720,
}
const readinessStyle: CSSProperties = {
  minHeight: 36, display: 'inline-flex', alignItems: 'center', flexShrink: 0, gap: 8, padding: '7px 11px',
  border: '1px solid var(--color-separator)', borderRadius: 'var(--r-chip)', background: 'var(--color-surface)',
  fontSize: 13, fontWeight: 650,
}
const dotStyle: CSSProperties = { width: 8, height: 8, borderRadius: '50%', flexShrink: 0 }
const noticeStyle: CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s-3)',
  padding: '14px 16px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)',
  background: 'var(--color-surface-elevated)', color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.5,
}
const noticeBodyStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0, flex: '1 1 300px' }
const noticeTitleStyle: CSSProperties = { color: 'var(--color-text-primary)', fontSize: 14 }
const reasonListStyle: CSSProperties = { margin: '4px 0 0', paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 5 }
const detailsStyle: CSSProperties = {
  borderTop: '1px solid var(--color-separator)', borderBottom: '1px solid var(--color-separator)',
  color: 'var(--color-text-secondary)', fontSize: 13,
}
const detailsSummaryStyle: CSSProperties = {
  minHeight: 44, display: 'flex', alignItems: 'center', cursor: 'pointer', color: 'var(--color-text-secondary)', fontWeight: 600,
}
const detailsBodyStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 6, padding: '0 0 12px', lineHeight: 1.45, overflowWrap: 'anywhere',
}
const workspaceStyle: CSSProperties = {
  display: 'grid', gridTemplateColumns: 'minmax(300px, .72fr) minmax(0, 1.28fr)', gap: 'var(--s-4)', alignItems: 'start', minWidth: 0,
}
const setupColumnStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 'var(--s-4)', minWidth: 0 }
const outputColumnStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 'var(--s-4)', minWidth: 0 }
const sectionStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 'var(--s-3)', minWidth: 0, padding: '16px',
  border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)', background: 'var(--color-surface)',
}
const resultsSectionStyle: CSSProperties = {
  ...sectionStyle, padding: '18px', boxShadow: 'var(--shadow-soft)',
}
const sectionHeaderStyle: CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--s-3)', minWidth: 0,
}
const sectionTitleStyle: CSSProperties = {
  margin: 0, fontFamily: 'var(--font-body)', fontSize: 18, lineHeight: 1.25, fontWeight: 720, color: 'var(--color-text-primary)',
}
const sectionDescriptionStyle: CSSProperties = {
  margin: '4px 0 0', fontSize: 14, lineHeight: 1.45, color: 'var(--color-text-secondary)',
}
const countStyle: CSSProperties = {
  flexShrink: 0, fontSize: 12, color: 'var(--color-text-muted)', paddingTop: 3,
}
const referenceStackStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 'var(--s-2)', minWidth: 0 }
const boundReferenceStyle: CSSProperties = {
  minHeight: 64, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--s-2)', minWidth: 0,
  padding: '10px 12px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-selected)',
}
const referenceEmptyStyle: CSSProperties = {
  minHeight: 64, display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
  border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)', color: 'var(--color-text-secondary)', minWidth: 0,
}
const referenceIdentityStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }
const referenceIconStyle: CSSProperties = {
  width: 36, height: 36, display: 'grid', placeItems: 'center', flexShrink: 0, borderRadius: 10,
  background: 'var(--color-surface-elevated)', color: 'var(--color-accent)',
}
const referenceNameStyle: CSSProperties = { display: 'block', color: 'var(--color-text-primary)', fontSize: 14, lineHeight: 1.35 }
const supportingTextStyle: CSSProperties = { color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.45, overflowWrap: 'anywhere' }
const quietIconButtonStyle: CSSProperties = {
  width: 44, height: 44, display: 'grid', placeItems: 'center', flexShrink: 0, border: 0, borderRadius: 'var(--r-control)',
  background: 'transparent', color: 'var(--color-text-secondary)', cursor: 'pointer',
}
const charControlStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 'var(--s-2)', width: '100%', minWidth: 0 }
const characterButtonStyle: CSSProperties = {
  minHeight: 44, width: '100%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
  border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '9px 12px', background: 'var(--color-surface)',
  color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 650, cursor: 'pointer',
}
const pickerPanelStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 'var(--s-2)', width: '100%', minWidth: 0, maxHeight: 'min(58dvh, 440px)', overflowY: 'auto',
  padding: '10px', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)',
}
const pickerSectionLabelStyle: CSSProperties = { fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)' }
const pickerEmptyStyle: CSSProperties = { padding: '8px 2px', color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.45 }
const pickerListStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }
const pickerItemStyle: CSSProperties = {
  minHeight: 48, display: 'flex', alignItems: 'center', gap: 9, width: '100%', padding: '6px 8px',
  border: '1px solid transparent', background: 'var(--color-surface)', cursor: 'pointer', color: 'var(--color-text-primary)',
  fontFamily: 'var(--font-body)', fontSize: 14, textAlign: 'left', borderRadius: 'var(--r-control)', minWidth: 0,
}
const pickerMetaStyle: CSSProperties = { flexShrink: 0, color: 'var(--color-text-muted)', fontSize: 12 }
const pickerDividerStyle: CSSProperties = { borderTop: '1px solid var(--color-separator)', margin: '2px 0' }
const popupFormStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }
const inputStyle: CSSProperties = {
  width: '100%', minHeight: 44, border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '9px 11px',
  background: 'var(--color-surface)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 16, outline: 'none',
}
const fileLabelStyle: CSSProperties = {
  minHeight: 44, display: 'flex', alignItems: 'center', gap: 8, border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)',
  padding: '9px 11px', fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer', minWidth: 0,
}
const anchorStyle: CSSProperties = {
  minHeight: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '10px 12px',
  borderRadius: 'var(--r-control)', background: 'var(--color-selected)', border: '1px solid var(--color-separator)', minWidth: 0,
}
const qualityBannerTitleStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 7, fontWeight: 650, color: 'var(--color-text-primary)' }
const qualityAdviceStyle: CSSProperties = { fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.4 }
const conversationStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }
const conversationEmptyStyle: CSSProperties = {
  padding: '10px 0', color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.5,
}
const turnStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 5, maxWidth: '92%', padding: '10px 12px',
  border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)',
  color: 'var(--color-text-primary)', fontSize: 14, lineHeight: 1.45, overflowWrap: 'anywhere',
}
const turnRoleStyle: CSSProperties = { fontSize: 12, color: 'var(--color-text-secondary)' }
const turnMetaStyle: CSSProperties = { fontSize: 12, color: 'var(--color-text-secondary)' }
const composerStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 10, padding: '12px', border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)', minWidth: 0,
}
const textareaStyle: CSSProperties = {
  width: '100%', minHeight: 118, resize: 'vertical', border: 0, outline: 0, background: 'transparent',
  color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 16, lineHeight: 1.55, overflowWrap: 'anywhere',
}
const controlsStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', minWidth: 0 }
const segmentedStyle: CSSProperties = {
  display: 'flex', gap: 2, border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: 2, background: 'var(--color-surface)',
}
const segmentButtonStyle: CSSProperties = {
  minWidth: 44, minHeight: 44, border: 0, borderRadius: 10, padding: '8px 11px', background: 'transparent',
  color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)', fontSize: 14, cursor: 'pointer',
}
const selectedSegmentStyle: CSSProperties = { background: 'var(--color-selected)', color: 'var(--color-accent)', fontWeight: 700 }
const selectStyle: CSSProperties = {
  minHeight: 44, maxWidth: '100%', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '8px 10px',
  background: 'var(--color-surface)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 14,
}
const actionRowStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', minWidth: 0 }
const estimateStyle: CSSProperties = { flex: '1 1 220px', minWidth: 0, fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.4 }
const sendButtonStyle: CSSProperties = {
  minHeight: 48, display: 'inline-flex', alignItems: 'center', gap: 8, border: 0, borderRadius: 'var(--r-control)', padding: '11px 16px',
  background: 'var(--color-accent)', color: 'var(--on-primary)', fontFamily: 'var(--font-body)', fontSize: 15, fontWeight: 720,
}
const secondaryButtonStyle: CSSProperties = {
  minHeight: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7, flexShrink: 0,
  border: '1px solid var(--color-separator)', borderRadius: 'var(--r-control)', padding: '8px 11px', background: 'var(--color-surface)',
  color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 650, cursor: 'pointer',
}
const errorStyle: CSSProperties = {
  padding: '10px 12px', border: '1px solid var(--color-destructive)', borderRadius: 'var(--r-control)',
  color: 'var(--color-destructive)', background: 'var(--color-surface)', fontSize: 13, lineHeight: 1.45,
}
const resultsEmptyStyle: CSSProperties = {
  minHeight: 260, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, textAlign: 'center',
  padding: '24px', border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)', color: 'var(--color-text-secondary)',
}
const batchResultsStackStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 'var(--s-4)', minWidth: 0 }
const resultBatchStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }
const resultBatchHeaderStyle: CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, minWidth: 0, paddingTop: 2,
  color: 'var(--color-text-primary)', fontSize: 14,
}
const statusBadgeStyle: CSSProperties = {
  flexShrink: 0, padding: '4px 7px', borderRadius: 'var(--r-chip)', background: 'var(--color-surface-elevated)',
  color: 'var(--color-text-secondary)', fontSize: 12, textTransform: 'capitalize',
}
const resultGridStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10, minWidth: 0 }
const resultCardStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }
const imageStyle: CSSProperties = {
  display: 'block', width: '100%', maxHeight: 620, objectFit: 'contain', borderRadius: 'var(--r-control)', background: 'var(--color-surface-elevated)',
}
const placeholderStyle: CSSProperties = {
  minHeight: 220, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 7,
  textAlign: 'center', border: '1px dashed var(--color-separator)', borderRadius: 'var(--r-control)', padding: '18px',
  color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 1.4, overflowWrap: 'anywhere',
}
const activityEmptyStyle: CSSProperties = { padding: '8px 0', color: 'var(--color-text-secondary)', fontSize: 14 }
const activityListStyle: CSSProperties = { display: 'flex', flexDirection: 'column', minWidth: 0 }
const activityRowStyle: CSSProperties = {
  minHeight: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, minWidth: 0,
  padding: '10px 0', borderTop: '1px solid var(--color-separator)',
}
const activityTitleStyle: CSSProperties = { color: 'var(--color-text-primary)', fontSize: 14, textTransform: 'lowercase' }
const failureTextStyle: CSSProperties = { marginTop: 4, color: 'var(--color-destructive)', fontSize: 13, overflowWrap: 'anywhere' }

function qualityBannerStyle(quality: RefQuality): CSSProperties {
  return {
    padding: '10px 12px', borderRadius: 'var(--r-control)', display: 'flex', flexDirection: 'column', gap: 4,
    background: 'var(--color-surface-elevated)',
    border: `1px solid ${quality.is_perfect ? 'var(--color-success)' : quality.has_blockers ? 'var(--color-destructive)' : 'var(--color-warning)'}`,
    fontFamily: 'var(--font-body)', fontSize: 13,
  }
}
