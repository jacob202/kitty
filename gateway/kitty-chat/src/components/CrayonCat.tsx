'use client'

type CatState = 'idle' | 'working' | 'done' | 'broke'

const FACES: Record<CatState, string> = {
  idle: '._.',
  working: 'o_o',
  done: '^_^',
  broke: ':[',
}

const STATE_DOTS: Record<CatState, string> = {
  idle: 'var(--cat-green)',
  working: 'var(--c-yellow)',
  done: 'var(--c-green)',
  broke: 'var(--c-red)',
}

export function CatCorner({ state = 'idle' }: { state?: CatState }) {
  return (
    <div style={{ position: 'fixed', bottom: 92, right: 26, zIndex: 30, pointerEvents: 'none' }}>
      <div className={`cat-${state}`}>
        <CatBody size={120} />
      </div>
    </div>
  )
}

export function CatMark() {
  return (
    <svg viewBox="0 0 160 150" style={{ width: 42, height: 'auto', display: 'block' }}>
      <g filter="url(#wob2)" opacity={0.9}>
        <circle cx={80} cy={92} r={50} fill="var(--cat-ginger)" />
        <path d="M52 52 L40 14 L84 46 Z" fill="var(--cat-ginger)" />
        <path d="M108 46 L122 14 L128 54 Z" fill="var(--cat-ginger)" />
        <circle cx={64} cy={88} r={7} fill="var(--cat-green)" />
        <circle cx={96} cy={88} r={7} fill="var(--cat-green)" />
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

export function CatBody({ size = 120 }: { size?: number }) {
  return (
    <svg viewBox="0 0 280 210" style={{ width: size, height: 'auto', display: 'block' }}>
      <g filter="url(#wob2)" opacity={0.9}>
        <ellipse cx={170} cy={129} rx={67} ry={51} fill="var(--cat-ginger)" />
        <circle cx={80} cy={102} r={49} fill="var(--cat-ginger)" />
        <path d="M55 64 L44 24 L86 57 Z" fill="var(--cat-ginger)" />
        <path d="M99 57 L118 24 L121 63 Z" fill="var(--cat-ginger)" />
        <path d="M58 56 L50 34 L74 53 Z" fill="var(--cat-pink)" />
        <path d="M102 54 L115 36 L116 60 Z" fill="var(--cat-pink)" />
        <circle cx={64} cy={95} r={8} fill="var(--cat-green)" />
        <path d="M38 104 L52 100 L49 112 Z" fill="var(--cat-pink)" />
        <circle cx={44} cy={114} r={6} fill="var(--cat-pink)" opacity={0.5} />
      </g>
      <g filter="url(#wob)" stroke="var(--cat-outline)" strokeWidth={5} fill="none" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx={168} cy={128} rx={62} ry={46} />
        <circle cx={80} cy={102} r={44} />
        <path d="M54 66 L44 24 L88 58" />
        <path d="M98 58 L118 24 L122 64" />
        <circle cx={64} cy={96} r={4.5} fill="var(--cat-outline)" stroke="none" />
        <path d="M38 104 L52 100 L49 112 Z" />
        <path d="M44 113 Q58 126 74 116" />
        <path d="M36 100 Q20 96 8 102 M38 114 Q22 116 10 124" />
        <path d="M120 168 q-4 18 6 20 M152 172 q-2 18 7 20 M188 170 q0 18 8 19 M214 160 q5 16 12 17" />
        <path d="M226 122 Q262 112 256 70 Q254 48 236 58" />
      </g>
    </svg>
  )
}

export function CatFaceBadge({ state = 'idle' }: { state?: CatState }) {
  return (
    <span style={{
      width: 30, height: 30, borderRadius: 99,
      background: 'var(--ginger-fade)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--font-mono)', fontSize: 11,
      color: 'var(--cat-ginger)', flexShrink: 0,
      border: '1.5px solid var(--line)',
    }}>
      {FACES[state]}
    </span>
  )
}

export function StateBadge({ state = 'idle' }: { state?: CatState }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)',
      border: '1.5px solid var(--line)', borderRadius: 99,
      padding: '3px 10px',
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: 99,
        background: STATE_DOTS[state],
      }} />
      {state}
    </span>
  )
}

export { FACES, STATE_DOTS }
export type { CatState }
