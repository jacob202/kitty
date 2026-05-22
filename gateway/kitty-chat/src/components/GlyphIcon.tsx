'use client'
import type { CSSProperties } from 'react'

export type GlyphId =
  | 'g-home'
  | 'g-chat'
  | 'g-check'
  | 'g-folder'
  | 'g-prompt'
  | 'g-spark'
  | 'g-cog'
  | 'g-search'
  | 'g-plus'
  | 'g-x'

interface Props {
  id: GlyphId
  size?: number
  style?: CSSProperties
  title?: string
}

export function GlyphIcon({ id, size = 18, style, title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      role={title ? 'img' : undefined}
      style={{ display: 'block', flexShrink: 0, ...style }}
    >
      <use href={`/glyphs.svg#${id}`} />
    </svg>
  )
}
