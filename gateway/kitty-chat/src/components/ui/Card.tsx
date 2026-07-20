'use client'
import type { ReactNode, CSSProperties } from 'react'

export interface CardProps {
  children: ReactNode
  padding?: 'sm' | 'md' | 'lg'
  style?: CSSProperties
  role?: string
  ariaLabel?: string
}

const paddings: Record<NonNullable<CardProps['padding']>, CSSProperties> = {
  sm: { padding: '10px 12px' },
  md: { padding: '14px 16px' },
  lg: { padding: '20px 24px' },
}

export function Card({ children, padding = 'md', style, role, ariaLabel }: CardProps) {
  return (
    <div
      role={role}
      aria-label={ariaLabel}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 12,
        ...paddings[padding],
        ...style,
      }}
    >
      {children}
    </div>
  )
}
