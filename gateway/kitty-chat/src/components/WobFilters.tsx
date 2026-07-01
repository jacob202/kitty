'use client'

export function WobFilters() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <filter id="wob" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" baseFrequency="0.015 0.02" numOctaves={2} seed={7} result="n" />
        <feDisplacementMap in="SourceGraphic" in2="n" scale={4.5} />
      </filter>
      <filter id="wob2" x="-30%" y="-30%" width="160%" height="160%">
        <feTurbulence type="fractalNoise" baseFrequency="0.02 0.028" numOctaves={2} seed={3} result="n" />
        <feDisplacementMap in="SourceGraphic" in2="n" scale={8} />
      </filter>
      <filter id="paper">
        <feTurbulence type="fractalNoise" baseFrequency={0.9} numOctaves={2} stitchTiles="stitch" />
      </filter>
    </svg>
  )
}

export function PaperGrain() {
  return (
    <svg
      style={{
        position: 'fixed', inset: 0, width: '100%', height: '100%',
        pointerEvents: 'none', zIndex: 40,
        opacity: 'var(--grain-opacity)' as unknown as number,
        mixBlendMode: 'var(--grain-blend)' as unknown as React.CSSProperties['mixBlendMode'],
      }}
      aria-hidden="true"
    >
      <rect width="100%" height="100%" filter="url(#paper)" />
    </svg>
  )
}
