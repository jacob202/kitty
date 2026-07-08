import type { CSSProperties, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'action' | 'ghost';

const actionButtonStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 700,
  padding: '2px 8px',
  borderRadius: 4,
  border: '1px solid var(--border)',
  cursor: 'pointer',
  background: 'var(--surface)',
  color: 'var(--text-muted)',
};

const primaryButtonStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  padding: '4px 12px',
  borderRadius: 4,
  border: 'none',
  cursor: 'pointer',
  background: 'var(--primary)',
  color: 'var(--on-primary)',
};

const ghostButtonStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  padding: '4px 12px',
  borderRadius: 4,
  border: '1px solid var(--border)',
  cursor: 'pointer',
  background: 'transparent',
  color: 'var(--text-muted)',
};

export function Button({
  children,
  variant = 'action',
  onClick,
  disabled,
  style,
  ariaLabel,
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  onClick?: () => void;
  disabled?: boolean;
  style?: CSSProperties;
  ariaLabel?: string;
}) {
  let baseStyle = actionButtonStyle;
  if (variant === 'primary') baseStyle = primaryButtonStyle;
  else if (variant === 'ghost') baseStyle = ghostButtonStyle;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      style={{
        ...baseStyle,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...style,
      }}
    >
      {children}
    </button>
  );
}
