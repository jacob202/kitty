import type { CSSProperties, ReactNode } from 'react';

export function Badge({
  children,
  tone = 'default',
  style,
}: {
  children: ReactNode;
  tone?: 'default' | 'error' | 'warn' | 'success';
  style?: CSSProperties;
}) {
  let color = 'var(--text-muted)';
  let bg = 'var(--surface-mid)';
  if (tone === 'error') {
    color = 'var(--error)';
    bg = 'var(--surface-error)'; // Assuming this exists or just dim
  } else if (tone === 'warn') {
    color = 'var(--c-yellow)';
  } else if (tone === 'success') {
    color = 'var(--c-green)';
  }

  return (
    <span
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        padding: '1px 5px',
        border: '1px solid var(--border)',
        borderRadius: 3,
        color,
        background: bg,
        ...style,
      }}
    >
      {children}
    </span>
  );
}
