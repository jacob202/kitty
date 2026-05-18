'use client'
import { KittyMood } from '@/lib/types'

interface Props {
  mood: KittyMood
  size?: number
}

export function MoodAvatar({ mood, size = 52 }: Props) {
  const face = {
    idle: { eyes: ['10px', '28px'], mouth: '18px', color: 'var(--orange)' },
    thinking: { eyes: ['11px', '27px'], mouth: '20px', color: 'var(--purple)' },
    success: { eyes: ['10px', '28px'], mouth: '16px', color: 'var(--teal)' },
    confused: { eyes: ['9px', '29px'], mouth: '22px', color: 'var(--yellow)' },
    searching: { eyes: ['8px', '30px'], mouth: '18px', color: 'var(--indigo)' },
  }[mood]

  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.23),
        flexShrink: 0,
        background: 'linear-gradient(180deg, var(--orange-2), var(--orange-deep))',
        border: `1.5px solid ${face.color}`,
        boxShadow: `0 0 14px color-mix(in srgb, ${face.color} 22%, transparent)`,
        imageRendering: 'pixelated',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        marginTop: 2,
      }}
      aria-label={`Kitty is ${mood}`}
    >
      <span style={{
        position: 'absolute',
        left: Math.round(size * 0.16),
        top: Math.round(size * 0.12),
        width: Math.round(size * 0.22),
        height: Math.round(size * 0.22),
        background: 'var(--orange-2)',
        clipPath: 'polygon(50% 0, 100% 100%, 0 100%)',
      }} />
      <span style={{
        position: 'absolute',
        right: Math.round(size * 0.16),
        top: Math.round(size * 0.12),
        width: Math.round(size * 0.22),
        height: Math.round(size * 0.22),
        background: 'var(--orange-2)',
        clipPath: 'polygon(50% 0, 100% 100%, 0 100%)',
      }} />
      <span style={{
        position: 'absolute',
        left: face.eyes[0],
        top: Math.round(size * 0.48),
        width: Math.max(4, Math.round(size * 0.11)),
        height: Math.max(4, Math.round(size * 0.11)),
        background: 'var(--bg)',
        borderRadius: 2,
      }} />
      <span style={{
        position: 'absolute',
        left: face.eyes[1],
        top: Math.round(size * 0.48),
        width: Math.max(4, Math.round(size * 0.11)),
        height: Math.max(4, Math.round(size * 0.11)),
        background: 'var(--bg)',
        borderRadius: 2,
      }} />
      <span style={{
        position: 'absolute',
        left: face.mouth,
        top: Math.round(size * 0.68),
        width: Math.max(8, Math.round(size * 0.18)),
        height: Math.max(3, Math.round(size * 0.07)),
        background: 'var(--bg)',
        borderRadius: 2,
      }} />
    </div>
  )
}
