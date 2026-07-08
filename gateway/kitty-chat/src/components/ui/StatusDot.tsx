import type { CSSProperties } from 'react';

export function StatusDot({
  tone,
  label,
  style,
}: {
  tone: 'ok' | 'warn' | 'bad';
  label: string;
  style?: CSSProperties;
}) {
  const color =
    tone === 'ok' ? 'var(--c-green)' : tone === 'warn' ? 'var(--c-yellow)' : 'var(--error)';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--text-dim)',
        ...style,
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
          display: 'inline-block',
        }}
      />
      {label}
    </span>
  );
}
