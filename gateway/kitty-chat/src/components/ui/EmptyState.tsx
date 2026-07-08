import type { CSSProperties, ReactNode } from 'react';
import { emptyState } from '@/lib/ui';

export function EmptyState({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div role="status" style={{ ...emptyState, ...style }}>
      {children}
    </div>
  );
}

export function ErrorState({ message, style }: { message: string; style?: CSSProperties }) {
  return (
    <div
      role="alert"
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--error)',
        textAlign: 'center',
        padding: '20px 0',
        ...style,
      }}
    >
      {message}
    </div>
  );
}
