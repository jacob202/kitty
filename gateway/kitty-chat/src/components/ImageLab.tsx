'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Image as ImageIcon, RefreshCw, Square, X } from 'lucide-react'
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

  const enginesAvailable = status.data?.available === true
    || (status.data?.engines ?? []).some(engine => engine.available)
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
        const session = await jsonOrError(sessionResponse)
        if (cancelled) return
        setSessionId(session.session_id)
        setAnchorJobId(session.anchor_job_id ?? null)
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
        window.localStorage.removeItem(SESSION_KEY)
        if (!cancelled) setSessionId(null)
      }
    })()
    return () => { cancelled = true }
  }, [])

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
      body: JSON.stringify({}),
    })
    const session = await jsonOrError(response)
    const id = String(session.session_id)
    setSessionId(id)
    window.localStorage.setItem(SESSION_KEY, id)
    return id
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
          <span>no image engine is online — generation stays disabled, but this workspace remains available</span>
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
            {anchorJobId && (
              <div data-testid="image-lab-anchor" style={anchorStyle}>
                editing from {anchorJobId}
                <button type="button" aria-label="clear selected image" onClick={() => setAnchorJobId(null)} style={iconButtonStyle}><X size={12} /></button>
              </div>
            )}
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
