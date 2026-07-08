import type { CSSProperties, ReactNode } from 'react';
import { sectionLabel } from '@/lib/ui';

export function SectionLabel({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div style={{ ...sectionLabel, ...style }}>
      {children}
    </div>
  );
}
