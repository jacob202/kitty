'use client'
import { KittyMood } from '@/lib/types'

interface Props {
  mood: KittyMood
  size?: number
}

const glowColor: Record<KittyMood, string> = {
  idle:      'var(--cat-ginger)',
  searching: 'var(--c-purple)',
  thinking:  'var(--c-purple)',
  success:   'var(--c-blue)',
  confused:  'var(--c-yellow)',
}

function Eyes({ mood }: { mood: KittyMood }) {
  switch (mood) {
    case 'idle':
      return (
        <>
          <circle cx="15" cy="22" r="3.5" fill="#1a1c1e"/>
          <circle cx="25" cy="22" r="3.5" fill="#1a1c1e"/>
          <circle cx="16" cy="21" r="1.2" fill="white"/>
          <circle cx="26" cy="21" r="1.2" fill="white"/>
        </>
      )
    case 'thinking':
      return (
        <>
          <circle cx="15" cy="22" r="3.5" fill="#1a1c1e"/>
          <circle cx="16" cy="21" r="1.2" fill="white"/>
          <path d="M22 22 Q25 19 28 22" stroke="#1a1c1e" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
          <path d="M20 14 Q21 12 22 13 Q23 14 22 15" stroke="#cfbdff" strokeWidth="1" fill="none"/>
        </>
      )
    case 'success':
      return (
        <>
          <path d="M12 23 Q15 19 18 23" stroke="#1a1c1e" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
          <path d="M22 23 Q25 19 28 23" stroke="#1a1c1e" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        </>
      )
    case 'confused':
      return (
        <>
          <ellipse cx="15" cy="22" rx="3.5" ry="2" fill="#1a1c1e"/>
          <ellipse cx="25" cy="22" rx="3.5" ry="2" fill="#1a1c1e"/>
          <line x1="12" y1="18" x2="18" y2="20" stroke="#1a1c1e" strokeWidth="1.5"/>
          <line x1="28" y1="18" x2="22" y2="20" stroke="#1a1c1e" strokeWidth="1.5"/>
        </>
      )
    case 'searching':
      return (
        <>
          <circle cx="15" cy="22" r="3.5" fill="#1a1c1e"/>
          <circle cx="25" cy="22" r="3.5" fill="#1a1c1e"/>
          <circle cx="17" cy="21" r="1.2" fill="white"/>
          <circle cx="27" cy="21" r="1.2" fill="white"/>
        </>
      )
  }
}

export function MoodAvatar({ mood, size = 52 }: Props) {
  const glow = glowColor[mood]
  return (
    <div
      aria-label={`Kitty is ${mood}`}
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.23),
        flexShrink: 0,
        border: `1.5px solid ${glow}`,
        boxShadow: `0 0 12px color-mix(in srgb, ${glow} 25%, transparent)`,
        transition: 'border-color 0.25s, box-shadow 0.25s',
        overflow: 'hidden',
      }}
    >
      <svg viewBox="0 0 40 40" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
        {/* Ears */}
        <polygon points="7,12 12,22 2,22" fill="#E8782A"/>
        <polygon points="33,12 38,22 28,22" fill="#E8782A"/>
        <polygon points="8,13 11,20 5,20" fill="#FFB4A1" opacity="0.7"/>
        <polygon points="32,13 37,20 27,20" fill="#FFB4A1" opacity="0.7"/>

        {/* Face */}
        <circle cx="20" cy="22" r="14" fill="#E8782A"/>

        {/* Forehead stripes */}
        <line x1="17" y1="9" x2="16" y2="13" stroke="#C5561A" strokeWidth="1.2" strokeLinecap="round"/>
        <line x1="20" y1="8" x2="20" y2="12" stroke="#C5561A" strokeWidth="1.2" strokeLinecap="round"/>
        <line x1="23" y1="9" x2="24" y2="13" stroke="#C5561A" strokeWidth="1.2" strokeLinecap="round"/>

        {/* Cheeks */}
        <circle cx="10" cy="26" r="3" fill="#FFB4A1" opacity="0.4"/>
        <circle cx="30" cy="26" r="3" fill="#FFB4A1" opacity="0.4"/>

        {/* Eyes (mood-dependent) */}
        <Eyes mood={mood}/>

        {/* Nose */}
        <path d="M18.5 27 L20 28.5 L21.5 27 Q20 26 18.5 27Z" fill="#7a2d1a"/>

        {/* Whiskers left */}
        <line x1="3" y1="25" x2="13" y2="25" stroke="#000" opacity="0.3" strokeWidth="0.8"/>
        <line x1="3" y1="27" x2="13" y2="27" stroke="#000" opacity="0.3" strokeWidth="0.8"/>

        {/* Whiskers right */}
        <line x1="27" y1="25" x2="37" y2="25" stroke="#000" opacity="0.3" strokeWidth="0.8"/>
        <line x1="27" y1="27" x2="37" y2="27" stroke="#000" opacity="0.3" strokeWidth="0.8"/>
      </svg>
    </div>
  )
}
