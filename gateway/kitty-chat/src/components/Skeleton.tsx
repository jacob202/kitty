'use client'
import type { CSSProperties } from 'react'

/** Static placeholder block. Use while a query is loading. */
export function Skeleton({ height = 60, width = '100%', radius = 8 }: {
  height?: number | string
  width?: number | string
  radius?: number
}) {
  return <div aria-hidden style={{ ...base, width, height, borderRadius: radius }} />
}

const base: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  opacity: 0.55,
}
