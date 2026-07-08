import { card, cardHeader, cardTitle, cardMeta, itemCard, bodyText } from '@/lib/ui';
import type { CSSProperties, ReactNode } from 'react';

export function Card({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}) {
  return <div style={{ ...card, ...style }}>{children}</div>;
}

export function CardHeader({
  title,
  count,
  action,
  style,
}: {
  title: string;
  count?: number | string;
  action?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div style={{ ...cardHeader, ...style }}>
      <span style={cardTitle}>{title}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {count !== undefined && <span style={cardMeta}>{count}</span>}
        {action}
      </div>
    </div>
  );
}

export function ItemCard({
  children,
  style,
  role,
  onClick,
  onKeyDown,
  onMouseEnter,
  onMouseLeave,
  tabIndex,
}: {
  children: ReactNode;
  style?: CSSProperties;
  role?: string;
  onClick?: () => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLDivElement>) => void;
  onMouseEnter?: (e: React.MouseEvent<HTMLDivElement>) => void;
  onMouseLeave?: (e: React.MouseEvent<HTMLDivElement>) => void;
  tabIndex?: number;
}) {
  return (
    <div
      role={role}
      tabIndex={tabIndex}
      style={{ ...itemCard, ...style }}
      onClick={onClick}
      onKeyDown={onKeyDown}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  );
}

export function BodyText({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}) {
  return <div style={{ ...bodyText, ...style }}>{children}</div>;
}
