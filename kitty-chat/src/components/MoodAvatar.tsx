'use client'
import { KittyMood } from '@/lib/types'
import { MOOD_SPRITE } from '@/lib/mood'

interface Props {
  mood: KittyMood
  size?: number
}

export function MoodAvatar({ mood, size = 52 }: Props) {
  const isSuccess = mood === 'success'
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.23),
        flexShrink: 0,
        backgroundImage: isSuccess
          ? "url('/mascots/kitty-mission.png')"
          : "url('/mascots/kitty-states.png')",
        backgroundSize: isSuccess ? '100% 100%' : '200% 200%',
        backgroundPosition: isSuccess ? '0% 0%' : MOOD_SPRITE[mood],
        border: '1.5px solid var(--purple-glow)',
        boxShadow: '0 0 14px color-mix(in srgb, var(--purple) 20%, transparent)',
        transition: 'background-position 0.35s ease, background-image 0.2s ease',
        marginTop: 2,
      }}
      aria-label={`Kitty is ${mood}`}
    />
  )
}
