'use client';
import { useState, type CSSProperties } from 'react';
import { X, Zap } from 'lucide-react';

export interface Signal {
  id: number;
  ts: number;
  source: string;
  kind: string;
  payload: {
    headline?: string;
    action?: string;
    analysis?: string;
    error?: string;
    [key: string]: unknown;
  };
}

interface Props {
  signal: Signal;
  onDismiss: (id: number) => void;
}

export function SignalCard({ signal, onDismiss }: Props) {
  const [expanded, setExpanded] = useState(false);
  const expertName = signal.source.replace('expert.', '');
  const headline = signal.payload.headline ?? signal.payload.error ?? signal.kind;
  const isError = signal.kind === 'expert.error';

  return (
    <div style={cardStyle}>
      <div style={headerStyle}>
        <Zap size={12} style={{ color: isError ? 'var(--c-red)' : 'var(--c-yellow)', flexShrink: 0 }} />
        <span style={sourceStyle}>{expertName}</span>
        <span style={headlineStyle}>{headline}</span>
        <button onClick={() => onDismiss(signal.id)} style={dismissStyle} title="dismiss">
          <X size={12} />
        </button>
      </div>
      {signal.payload.action && !expanded && (
        <button onClick={() => setExpanded(true)} style={expandStyle}>
          show details
        </button>
      )}
      {expanded && signal.payload.action && (
        <div style={detailStyle}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>suggested action</div>
          <div>{signal.payload.action}</div>
          {signal.payload.analysis && (
            <>
              <div style={{ fontWeight: 600, marginTop: 8, marginBottom: 4 }}>analysis</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{signal.payload.analysis}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function SignalFeed({
  signals,
  onDismiss,
}: {
  signals: Signal[];
  onDismiss: (id: number) => void;
}) {
  if (!signals.length) return null;
  return (
    <div style={feedStyle}>
      {signals.map((s) => (
        <SignalCard key={s.id} signal={s} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

const feedStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: '8px 0',
};

const cardStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1.5px solid var(--line)',
  borderRadius: 10,
  padding: '8px 12px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
};

const headerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

const sourceStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: '0.05em',
  color: 'var(--ink-2)',
  flexShrink: 0,
};

const headlineStyle: CSSProperties = {
  flex: 1,
  fontSize: 13,
  fontWeight: 500,
  color: 'var(--ink)',
  lineHeight: 1.4,
};

const dismissStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--ink-2)',
  padding: 2,
  borderRadius: 4,
  flexShrink: 0,
};

const expandStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--ink-2)',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: 0,
  textAlign: 'left',
};

const detailStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  lineHeight: 1.5,
  color: 'var(--ink-2)',
  borderTop: '1px solid var(--line)',
  paddingTop: 6,
};
