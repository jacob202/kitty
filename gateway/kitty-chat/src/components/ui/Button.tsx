'use client'
import type { ReactNode, CSSProperties } from 'react'

export interface ButtonProps {
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  icon?: ReactNode
  children: ReactNode
  title?: string
  ariaLabel?: string
  type?: 'button' | 'submit'
}

const variantStyles: Record<NonNullable<ButtonProps['variant']>, CSSProperties> = {
  primary: {
    background: 'var(--primary)',
    color: 'var(--on-primary)',
    border: 'none',
    boxShadow: 'var(--btn-shadow)',
  },
  secondary: {
    background: 'var(--surface)',
    color: 'var(--ink)',
    border: '1px solid var(--line)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--ink-2)',
    border: 'none',
  },
  danger: {
    background: 'transparent',
    color: 'var(--c-red)',
    border: '1px solid var(--c-red)',
  },
}

const sizeStyles: Record<NonNullable<ButtonProps['size']>, CSSProperties> = {
  sm: { padding: '4px 10px', fontSize: 12, borderRadius: 8, minHeight: 32 },
  md: { padding: '8px 16px', fontSize: 14, borderRadius: 10, minHeight: 44 },
  lg: { padding: '12px 24px', fontSize: 16, borderRadius: 12, minHeight: 48 },
}

export function Button({
  onClick,
  variant = 'primary',
  size = 'md',
  disabled,
  loading,
  icon,
  children,
  title,
  ariaLabel,
  type = 'button',
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
      aria-label={ariaLabel}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        fontFamily: 'var(--font-body)',
        fontWeight: 600,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'opacity 0.15s ease, transform 0.1s ease',
        ...variantStyles[variant],
        ...sizeStyles[size],
      }}
    >
      {loading ? (
        <span style={{
          width: size === 'sm' ? 12 : 14,
          height: size === 'sm' ? 12 : 14,
          border: '2px solid currentColor',
          borderTopColor: 'transparent',
          borderRadius: '50%',
          display: 'inline-block',
          animation: 'throb 0.8s linear infinite',
        }} />
      ) : icon ? (
        <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>
      ) : null}
      {children}
    </button>
  )
}
