'use client'
import type { CSSProperties } from 'react'

type Shape = 'line' | 'card' | 'circle'

const shapeDefaults: Record<Shape, Partial<CSSProperties>> = {
  line:   { height: 16, width: '100%', borderRadius: 4 },
  card:   { height: 120, width: '100%', borderRadius: 8 },
  circle: { height: 48, width: 48, borderRadius: '50%' },
}

/** Shimmer placeholder. Use while content is loading. */
export function Skeleton({ height, width, radius, shape }: {
  height?: number | string
  width?: number | string
  radius?: number
  shape?: Shape
}) {
  const s = shape ? shapeDefaults[shape] : {}
  return (
    <div
      aria-hidden
      className="skeleton-shimmer"
      style={{ ...base, width: width ?? s.width, height: height ?? s.height, borderRadius: radius ?? s.borderRadius }}
    />
  )
}

const base: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--line)',
}
