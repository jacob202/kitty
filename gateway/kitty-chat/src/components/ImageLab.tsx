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
        setCharacters(payload.characters ?? [])
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
    const character = await response.json() as StudioCharacter
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
      body: JSON.stringify({ quality, identity, count }),
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
  }, [quality, identity, count])

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

  return (
    <section style={shellStyle} aria-label="Image Lab">
      <header style={headerStyle}>
        <div>
          <h1 style={titleStyle}>Image Lab</h1>
          <p style={subtitleStyle}>Talk through the image. Kitty handles the generation plan; your results and queue stay here.</p>
        </div>
        <div style={statusStyle}>
          <span style={{ ...dotStyle, background: enginesAvailable ? 'var(--c-green)' : 'var(--c-red)' }} />
          {status.isError ? 'image service unavailable' : enginesAvailable ? 'renderer ready' : 'renderer offline'}
        </div>
      </header>

      {status.isError && (
        <div role="alert" style={noticeStyle}>
          can’t reach Kitty’s image service
          <button type="button" onClick={() => void status.refetch()} style={smallButtonStyle}>check again</button>
        </div>
      )}
      {!status.isError && !status.isPending && !enginesAvailable && (
        <div role="status" style={noticeStyle}>
          <div style={noticeBodyStyle}>
            <span>no image engine is online — generation stays disabled, but this workspace remains available</span>
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
          <button type="button" onClick={() => void status.refetch()} style={smallButtonStyle}>check again</button>
        </div>
      )}

      <div
        data-testid="image-lab-workspace"
        style={{ ...workspaceStyle, ...(compact ? { gridTemplateColumns: '1fr' } : {}) }}
      >
        <div style={conversationStyle}>
          {turns.length === 0 && (
            <div style={emptyStyle}>
              Drop into the work: describe the image, the change, or which result you want to build from.
            </div>
          )}
          {turns.map(turn => (
            <div key={turn.id} style={{ ...turnStyle, alignSelf: turn.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <strong style={turnRoleStyle}>{turn.role === 'user' ? 'you' : 'kitty'}</strong>
              <span>{turn.text}</span>
              {turn.protectedTraits && turn.protectedTraits.length > 0 && (
                <span style={metaStyle}>staying fixed: {turn.protectedTraits.join(', ')}</span>
              )}
              {turn.requestedChanges && turn.requestedChanges.length > 0 && (
                <span style={metaStyle}>changing: {turn.requestedChanges.join(', ')}</span>
              )}
            </div>
          ))}

          <div style={composerStyle}>
            <div style={chipRowStyle}>
              {anchorJobId && (
                <div data-testid="image-lab-anchor" style={anchorStyle}>
                  editing from {anchorJobId}
                  <button type="button" aria-label="clear selected image" onClick={() => void clearAnchor()} style={iconButtonStyle}><X size={12} /></button>
                </div>
              )}
              <div style={charControlStyle}>
                {selectedCharacter ? (
                  <span data-testid="image-lab-character" style={anchorStyle}>
                    <User size={12} />
                    {selectedCharacter.name}
                    {selectedCharacter.references.length === 0 && <em style={metaStyle}>no ref</em>}
                    <button type="button" aria-label="clear reference character" onClick={() => void clearCharacter()} style={iconButtonStyle}><X size={12} /></button>
                  </span>
                ) : (
                  <button type="button" data-testid="image-lab-character-picker" onClick={() => setShowCharPicker(open => !open)} style={characterButtonStyle}>
                    <User size={12} /> reference
                  </button>
                )}
                {showCharPicker && (
                  <div style={popupStyle}>
                    <div style={popupHeaderStyle}>saved characters</div>
                    {charactersLoading ? (
                      <div style={popupItemMutedStyle}>loading…</div>
                    ) : characters.length === 0 ? (
                      <div style={popupItemMutedStyle}>no saved characters yet — create one below</div>
                    ) : (
                      characters.map(character => (
                        <button key={character.character_id} type="button" onClick={() => void bindCharacter(character)} style={pickerItemStyle}>
                          <User size={13} />
                          <span>{character.name}</span>
                          {character.references.length === 0 && <span style={popupItemMutedStyle}>no ref</span>}
                        </button>
                      ))
                    )}
                    <div style={popupDividerStyle} />
                    <div style={popupFormStyle}>
                      <input
                        type="text"
                        value={newCharName}
                        onChange={event => setNewCharName(event.target.value)}
                        onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void createNewCharacter() } }}
                        placeholder="new character name"
                        style={inputStyle}
                      />
                      <label style={fileLabelStyle}>
                        <Upload size={12} />
                        <span>{charRefFile ? charRefFile.name : 'reference photo'}</span>
                        <input type="file" accept="image/*" onChange={event => setCharRefFile(event.target.files?.[0] ?? null)} style={{ display: 'none' }} />
                      </label>
                      <button
                        type="button"
                        data-testid="image-lab-create-character"
                        disabled={!newCharName.trim() || charUploading}
                        onClick={() => void createNewCharacter()}
                        style={{ ...smallButtonStyle, opacity: !newCharName.trim() || charUploading ? 0.45 : 1 }}
                      >
                        {charUploading ? 'creating…' : 'create'}
                      </button>
                    </div>
                    {refQuality && (
                      <div style={qualityBannerStyle(refQuality)}>
                        <div style={qualityBannerTitleStyle}>
                          {refQuality.is_perfect
                            ? <CheckCircle2 size={13} style={{ color: 'var(--c-green)' }} />
                            : <AlertTriangle size={13} style={{ color: refQuality.has_blockers ? 'var(--c-red)' : 'var(--c-yellow)' }} />}
                          <span>{refQuality.summary}</span>
                        </div>
                        {refQuality.dimensions && <span style={metaStyle}>{refQuality.dimensions}</span>}
                        {refQuality.advice.map((advice, index) => (
                          <div key={index} style={qualityAdviceStyle}>{advice}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
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
              rows={3}
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
                <option value="fast">fast</option>
                <option value="quality">quality</option>
                <option value="maximum">maximum</option>
              </select>
              <select aria-label="identity" value={identity} onChange={event => setIdentity(event.target.value as IdentityMode)} style={selectStyle}>
                <option value="creative">creative</option>
                <option value="balanced">balanced</option>
                <option value="identity_first">identity first</option>
              </select>
              <span data-testid="image-lab-estimate" style={estimateStyle}>{estimateText}</span>
              <button
                type="button"
                data-testid="image-lab-send"
                disabled={!enginesAvailable || busy || !prompt.trim()}
                onClick={() => void send()}
                style={{ ...sendButtonStyle, opacity: !enginesAvailable || busy || !prompt.trim() ? 0.45 : 1 }}
              >
                {busy ? <RefreshCw size={14} /> : <ImageIcon size={14} />}
                {busy ? 'planning…' : 'queue'}
              </button>
            </div>
          </div>
          {error && <div role="alert" style={errorStyle}>{error}</div>}
        </div>

        <aside style={queueStyle} aria-label="Image queue and results">
          <div style={queueHeaderStyle}>
            <strong>Queue & results</strong>
            <span style={metaStyle}>{batches.length} batch{batches.length === 1 ? '' : 'es'}</span>
          </div>
          {batches.length === 0 ? (
            <div style={emptyStyle}>Queued work and completed images will stay here.</div>
          ) : batches.map(batch => (
            <div key={batch.batch_id} style={batchStyle}>
              <div style={batchHeaderStyle}>
                <span>{batch.count} image{batch.count === 1 ? '' : 's'} {batch.status}</span>
                {(batch.status === 'queued' || batch.status === 'running') && (
                  <button type="button" onClick={() => void cancelBatch(batch.batch_id)} style={smallButtonStyle}>
                    <Square size={10} /> cancel queued
                  </button>
                )}
              </div>
              <div style={metaStyle}>{batch.request?.prompt ?? ''}</div>
              <div style={resultGridStyle}>
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
                          <button type="button" onClick={() => void useThis(item.job_id as string)} style={smallButtonStyle}>
                            use this
                          </button>
                        )}
                      </>
                    ) : (
                      <div style={placeholderStyle}>
                        {item.status === 'running' ? 'generating…' : item.status === 'failed' ? item.error || 'failed' : item.status}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </aside>
      </div>
    </section>
  )
}

const shellStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 16, width: '100%', minHeight: '100%' }
const headerStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start' }
const titleStyle: CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 30, color: 'var(--ink)' }
const subtitleStyle: CSSProperties = { margin: '4px 0 0', fontSize: 13, color: 'var(--ink-2)', maxWidth: 680 }
const statusStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const dotStyle: CSSProperties = { width: 7, height: 7, borderRadius: '50%' }
const noticeStyle: CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 10, color: 'var(--ink-2)', fontSize: 12 }
const noticeBodyStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }
const reasonListStyle: CSSProperties = { margin: 0, paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 4 }
const workspaceStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(280px, .8fr)', gap: 16, alignItems: 'start' }
const conversationStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }
const turnStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, maxWidth: '86%', padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)' }
const turnRoleStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--ink-2)' }
const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--ink-2)' }
const composerStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, padding: 12, border: '1px solid var(--line)', borderRadius: 14, background: 'var(--surface)' }
const textareaStyle: CSSProperties = { width: '100%', resize: 'vertical', border: 0, outline: 0, background: 'transparent', color: 'var(--ink)', fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: 1.5 }
const controlsStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }
const segmentedStyle: CSSProperties = { display: 'flex', gap: 2, border: '1px solid var(--line)', borderRadius: 8, padding: 2 }
const segmentButtonStyle: CSSProperties = { border: 0, borderRadius: 6, padding: '4px 8px', background: 'transparent', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 10, cursor: 'pointer' }
const selectedSegmentStyle: CSSProperties = { background: 'var(--ginger-fade)', color: 'var(--cat-ginger)' }
const selectStyle: CSSProperties = { border: '1px solid var(--line)', borderRadius: 8, padding: '5px 7px', background: 'var(--bg)', color: 'var(--ink)', fontFamily: 'var(--font-mono)', fontSize: 10 }
const estimateStyle: CSSProperties = { flex: 1, minWidth: 170, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--ink-2)' }
const sendButtonStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 6, border: 0, borderRadius: 8, padding: '7px 10px', background: 'var(--primary)', color: 'var(--on-primary)', fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }
const queueStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }
const queueHeaderStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }
const batchStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, border: '1px solid var(--line)', borderRadius: 12, padding: 10, background: 'var(--surface)' }
const batchHeaderStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600 }
const resultGridStyle: CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }
const resultCardStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }
const imageStyle: CSSProperties = { width: '100%', aspectRatio: '1', objectFit: 'cover', borderRadius: 8, background: 'var(--bg)' }
const placeholderStyle: CSSProperties = { minHeight: 100, display: 'grid', placeItems: 'center', textAlign: 'center', border: '1px dashed var(--line)', borderRadius: 8, padding: 8, color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 9 }
const emptyStyle: CSSProperties = { padding: 14, border: '1px dashed var(--line)', borderRadius: 10, color: 'var(--ink-2)', fontSize: 12 }
const errorStyle: CSSProperties = { padding: '9px 11px', border: '1px solid var(--c-red)', borderRadius: 8, color: 'var(--c-red)', fontSize: 12 }
const smallButtonStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 4, border: '1px solid var(--line)', borderRadius: 7, padding: '4px 7px', background: 'transparent', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 9, cursor: 'pointer' }
const anchorStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', alignSelf: 'flex-start', gap: 5, padding: '4px 7px', borderRadius: 999, background: 'var(--ginger-fade)', color: 'var(--cat-ginger)', fontFamily: 'var(--font-mono)', fontSize: 9 }
const iconButtonStyle: CSSProperties = { border: 0, background: 'transparent', color: 'inherit', padding: 0, cursor: 'pointer', display: 'inline-flex' }
const chipRowStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }
const charControlStyle: CSSProperties = { position: 'relative' }
const characterButtonStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 5, border: '1px solid var(--line)', borderRadius: 999, padding: '4px 8px', background: 'transparent', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 9, cursor: 'pointer' }
const popupStyle: CSSProperties = { position: 'absolute', top: '100%', left: 0, marginTop: 4, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, minWidth: 240, maxWidth: 'min(320px, calc(100vw - 40px))', maxHeight: 'min(60dvh, 360px)', overflowY: 'auto', zIndex: 100, boxShadow: 'var(--shadow)', padding: 6 }
const popupHeaderStyle: CSSProperties = { padding: '4px 8px 6px', fontFamily: 'var(--font-mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--ink-2)' }
const popupItemMutedStyle: CSSProperties = { padding: '6px 8px', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--ink-2)' }
const pickerItemStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 8px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--ink)', fontFamily: 'var(--font-body)', fontSize: 13, textAlign: 'left', borderRadius: 8 }
const popupDividerStyle: CSSProperties = { borderTop: '1px solid var(--line)', margin: '6px 0' }
const popupFormStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6, padding: '0 8px 6px' }
const inputStyle: CSSProperties = { width: '100%', border: '1px solid var(--line)', borderRadius: 8, padding: '6px 8px', background: 'var(--bg)', color: 'var(--ink)', fontFamily: 'var(--font-mono)', fontSize: 11, outline: 'none' }
const fileLabelStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, border: '1px dashed var(--line)', borderRadius: 8, padding: '6px 8px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', cursor: 'pointer', overflow: 'hidden' }
const qualityBannerTitleStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }
const qualityAdviceStyle: CSSProperties = { fontSize: 10, color: 'var(--ink-2)', marginTop: 3 }
function qualityBannerStyle(quality: RefQuality): CSSProperties {
  return {
    marginTop: 6, padding: '8px 10px', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 2,
    background: quality.is_perfect ? 'rgba(127, 176, 105, 0.10)' : quality.has_blockers ? 'rgba(217, 122, 102, 0.12)' : 'rgba(232, 196, 106, 0.10)',
    border: `1px solid ${quality.is_perfect ? 'var(--c-green)' : quality.has_blockers ? 'var(--c-red)' : 'var(--c-yellow)'}`,
    fontFamily: 'var(--font-body)', fontSize: 10,
  }
}
