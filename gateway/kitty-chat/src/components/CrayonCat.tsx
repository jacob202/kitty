'use client'

import { useReducedMotion } from '@/hooks/useReducedMotion'

export type CatState = 'idle' | 'working' | 'done' | 'broke'

const EYE_COLORS: Record<CatState, string> = {
  idle: 'var(--cat-green)',
  working: 'var(--c-yellow)',
  done: 'var(--c-green)',
  broke: 'var(--c-red)',
}

// ── Corner avatar (bottom-right mascot) ──────────────────────────────

export function CatCorner({ state = 'idle' }: { state?: CatState }) {
  const reducedMotion = useReducedMotion()

  return (
    <div
      className="cat-corner"
      style={{
        position: 'fixed',
        bottom: 92,
        right: 26,
        zIndex: 30,
        pointerEvents: 'none',
      }}
      aria-hidden
    >
      <div className={`cat-${state}${reducedMotion ? '' : ' cat-animate'}`}>
        <CatBody state={state} size={120} />
      </div>
    </div>
  )
}

// ── Mini badge (inline, for status bars / headers) ──────────────────

export function CatMark({ state = 'idle' }: { state?: CatState }) {
  const eye = EYE_COLORS[state]
  return (
    <svg viewBox="0 0 160 150" style={{ width: 42, height: 'auto', display: 'block' }}>
      <defs>
        <filter id="wob2">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="2.5" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="wob">
          <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="1" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.2" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
      <g filter="url(#wob2)" opacity={0.9}>
        <circle cx={80} cy={92} r={50} fill="var(--cat-ginger)" />
        <path d="M52 52 L40 14 L84 46 Z" fill="var(--cat-ginger)" />
        <path d="M108 46 L122 14 L128 54 Z" fill="var(--cat-ginger)" />
        <circle cx={64} cy={88} r={7} fill={eye} />
        <circle cx={96} cy={88} r={7} fill={eye} />
      </g>
      <g filter="url(#wob)" stroke="var(--cat-outline)" strokeWidth={6} fill="none" strokeLinecap="round" strokeLinejoin="round">
        <circle cx={80} cy={92} r={46} />
        <path d="M52 54 L40 16 L82 48" />
        <path d="M104 48 L122 16 L126 56" />
        <circle cx={64} cy={89} r={4} fill="var(--cat-outline)" stroke="none" />
        <circle cx={96} cy={89} r={4} fill="var(--cat-outline)" stroke="none" />
        <path d="M74 100 Q80 106 86 100" />
      </g>
    </svg>
  )
}

// ── Main body with expressive face ───────────────────────────────────

export function CatBody({ state = 'idle', size = 120 }: { state?: CatState; size?: number }) {
  const eye = EYE_COLORS[state]
  const eyeL = leftEye(state)
  const eyeR = rightEye(state)
  const mouth = catMouth(state)

  return (
    <svg viewBox="0 0 280 210" style={{ width: size, height: 'auto', display: 'block' }}>
      <defs>
        <filter id="wob3" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="wob4" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="1" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.5" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>

      {/* Body fill */}
      <g filter="url(#wob3)" opacity={0.85}>
        <ellipse cx={170} cy={129} rx={67} ry={51} fill="var(--cat-ginger)" />
        <circle cx={80} cy={102} r={49} fill="var(--cat-ginger)" />
        <path d="M55 64 L44 24 L86 57 Z" fill="var(--cat-ginger)" />
        <path d="M99 57 L118 24 L121 63 Z" fill="var(--cat-ginger)" />
        {/* Inner ears */}
        <path d="M58 56 L50 34 L74 53 Z" fill="var(--cat-pink)" />
        <path d="M102 54 L115 36 L116 60 Z" fill="var(--cat-pink)" />

        {/* Eyes — expressive */}
        {eyeL}
        {eyeR}

        {/* Nose */}
        <path d="M38 104 L52 100 L49 112 Z" fill="var(--cat-pink)" />

        {/* Cheek blush */}
        <circle cx={44} cy={114} r={6} fill="var(--cat-pink)" opacity={0.3} />
      </g>

      {/* Ink outline */}
      <g filter="url(#wob4)" stroke="var(--cat-outline)" strokeWidth={4.5} fill="none" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx={168} cy={128} rx={60} ry={44} />
        <circle cx={80} cy={102} r={44} />
        <path d="M54 66 L44 24 L88 58" />
        <path d="M98 58 L118 24 L122 64" />
        {/* Eye outlines */}
        {outlineEyes(state)}
        {/* Nose + mouth */}
        <path d="M38 104 L52 100 L49 112 Z" />
        {mouth}
        {/* Whiskers */}
        <path d="M36 100 Q20 96 8 102 M38 114 Q22 116 10 124" />
        {/* Paws */}
        <path d="M120 168 q-4 18 6 20 M152 172 q-2 18 7 20 M188 170 q0 18 8 19 M214 160 q5 16 12 17" />
        {/* Tail */}
        <path d="M226 122 Q262 112 256 70 Q254 48 236 58" />
      </g>

      {/* Done sparkle */}
      {state === 'done' && <Sparkle />}
    </svg>
  )
}

// ── Expression helpers ────────────────────────────────────────────────

function leftEye(state: CatState) {
  switch (state) {
    case 'idle':
      return <ellipse cx={64} cy={96} rx={7} ry={2.5} fill="var(--cat-green)" />
    case 'working':
      return <circle cx={64} cy={95} r={6} fill="var(--c-yellow)" />
    case 'done':
      return <path d="M56 95 Q64 83 72 95" stroke="var(--c-green)" strokeWidth={3} fill="none" strokeLinecap="round" />
    case 'broke':
      return <circle cx={64} cy={96} r={3} fill="var(--c-red)" />
  }
}

function rightEye(state: CatState) {
  switch (state) {
    case 'idle':
      return <ellipse cx={96} cy={96} rx={7} ry={2.5} fill="var(--cat-green)" />
    case 'working':
      return <circle cx={96} cy={95} r={6} fill="var(--c-yellow)" />
    case 'done':
      return <path d="M88 95 Q96 83 104 95" stroke="var(--c-green)" strokeWidth={3} fill="none" strokeLinecap="round" />
    case 'broke':
      return <circle cx={96} cy={96} r={3} fill="var(--c-red)" />
  }
}

function outlineEyes(state: CatState) {
  switch (state) {
    case 'done':
      return (
        <>
          <path d="M56 95 Q64 83 72 95" stroke="var(--cat-outline)" strokeWidth={2.5} fill="none" strokeLinecap="round" />
          <path d="M88 95 Q96 83 104 95" stroke="var(--cat-outline)" strokeWidth={2.5} fill="none" strokeLinecap="round" />
        </>
      )
    default:
      return (
        <>
          <circle cx={64} cy={96} r={4} fill="var(--cat-outline)" stroke="none" />
          <circle cx={96} cy={96} r={4} fill="var(--cat-outline)" stroke="none" />
        </>
      )
  }
}

function catMouth(state: CatState) {
  switch (state) {
    case 'idle':
      return <path d="M74 106 Q80 108 86 106" />
    case 'working':
      return <path d="M72 107 L80 109 L88 107" />
    case 'done':
      return <path d="M70 104 Q80 116 90 104" />
    case 'broke':
      return <path d="M72 110 Q80 106 88 110" />
  }
}

function Sparkle() {
  return (
    <g>
      <text x={20} y={50} fontSize={14} style={{ fontFamily: 'sans-serif' }}>✦</text>
      <text x={225} y={45} fontSize={10} style={{ fontFamily: 'sans-serif' }}>✦</text>
    </g>
  )
}

// ── Badge exports (compact status indicators) ────────────────────────

const LABELS: Record<CatState, string> = {
  idle: 'ready',
  working: 'thinking',
  done: 'done',
  broke: 'issue',
}

export function CatFaceBadge({ state = 'idle' }: { state?: CatState }) {
  const eye = EYE_COLORS[state]
  return (
    <span style={{
      width: 24,
      height: 24,
      borderRadius: 99,
      background: 'var(--ginger-fade)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1.5px solid var(--line)',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      <div style={{
        width: 10,
        height: 10,
        borderRadius: 99,
        background: eye,
        boxShadow: `0 0 4px ${eye}`,
      }} />
    </span>
  )
}

export function StateBadge({ state = 'idle' }: { state?: CatState }) {
  const eye = EYE_COLORS[state]
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      fontSize: 11,
      color: 'var(--ink-2)',
      border: '1.5px solid var(--line)',
      borderRadius: 99,
      padding: '3px 10px',
      fontFamily: 'var(--font-mono)',
    }}>
      <span style={{
        width: 7,
        height: 7,
        borderRadius: 99,
        background: eye,
        boxShadow: state === 'working' ? `0 0 6px ${eye}` : undefined,
      }} />
      {LABELS[state]}
    </span>
  )
}
