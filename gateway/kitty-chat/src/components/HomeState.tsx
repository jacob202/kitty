'use client';
import { useState } from 'react';
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState, bodyText } from '@/lib/ui';
import { CapturePanel } from '@/components/CapturePanel';
import {
  useStateChanges,
  useActions,
  useApproveAction,
  useRejectAction,
  useTodos,
  useLoops,
  useNeedsJacob,
  useSnapshotState,
  useRunInboxTriage,
  useStateNow,
} from '@/lib/queries';
import type { GatewayAction, GatewayTriageEntry, StateChange } from '@/lib/gateway';

// ── shared micro-components ──────────────────────────────────────────────────

function SectionCard({
  title,
  count,
  action,
  children,
}: {
  title: string;
  count?: number | string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div style={{ ...card, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={cardHeader}>
        <span style={cardTitle}>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {count !== undefined && <span style={cardMeta}>{count}</span>}
          {action}
        </div>
      </div>
      {children}
    </div>
  );
}

const actionButtonStyle: React.CSSProperties = {
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

function ErrorCard({ message }: { message: string }) {
  return (
    <div
      role="alert"
      style={{ ...itemCard, color: 'var(--error)', fontFamily: 'var(--font-mono)', fontSize: 11 }}
    >
      {message}
    </div>
  );
}

// ── What changed panel ───────────────────────────────────────────────────────

function WhatChanged() {
  const { data, isError, isPending } = useStateChanges();
  const snapshot = useSnapshotState();

  const markPoint = (
    <button
      type="button"
      disabled={snapshot.isPending}
      onClick={() => snapshot.mutate()}
      style={actionButtonStyle}
    >
      {snapshot.isPending ? '…' : 'mark point'}
    </button>
  );

  if (isPending) {
    return (
      <SectionCard title="what changed">
        <div role="status" style={{ ...emptyState }}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (isError || !data) {
    return (
      <SectionCard title="what changed">
        <ErrorCard message="gateway offline — changes unavailable" />
      </SectionCard>
    );
  }

  const { changes, new_signals, note } = data;
  const count = changes.length + new_signals.length;

  return (
    <SectionCard title="what changed" count={count || undefined} action={markPoint}>
      {note && !changes.length && !new_signals.length ? <div style={emptyState}>{note}</div> : null}
      {changes.map((c: StateChange, i: number) => (
        <div key={i} style={itemCard}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              marginBottom: 4,
            }}
          >
            {c.section}
            {c.field ? ` · ${c.field}` : ''}
          </div>
          <div style={bodyText}>
            {String(c.before ?? '–')} → {String(c.after ?? '–')}
          </div>
        </div>
      ))}
      {new_signals.length > 0 && (
        <div
          style={{
            ...itemCard,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={bodyText}>
            {new_signals.length} new signal{new_signals.length !== 1 ? 's' : ''} since last snapshot
          </span>
        </div>
      )}
      {!count && !note && <div style={emptyState}>nothing new since last snapshot</div>}
    </SectionCard>
  );
}

// ── Needs you (action queue) ─────────────────────────────────────────────────

function NeedsYou({ onDecideInChat }: { onDecideInChat: (entry: GatewayTriageEntry) => void }) {
  const { data: actions = [], isError, isPending } = useActions('proposed');
  const needsJacob = useNeedsJacob();
  const approve = useApproveAction();
  const reject = useRejectAction();
  // Track which action is in-flight to disable its buttons and prevent races.
  const [pendingId, setPendingId] = useState<number | null>(null);

  if (isPending || needsJacob.isPending) {
    return (
      <SectionCard title="needs you">
        <div role="status" style={emptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (isError) {
    return (
      <SectionCard title="needs you">
        <ErrorCard message="gateway offline — action queue unavailable" />
      </SectionCard>
    );
  }

  const needsJacobEntries = needsJacob.data?.entries ?? [];
  const total = actions.length + needsJacobEntries.length;

  const handleApprove = async (id: number) => {
    setPendingId(id);
    try {
      await approve.mutateAsync(id);
    } catch {
      // gateway error — button re-enables via finally
    } finally {
      setPendingId(null);
    }
  };

  const handleReject = async (id: number) => {
    setPendingId(id);
    try {
      await reject.mutateAsync(id);
    } catch {
      // gateway error — button re-enables via finally
    } finally {
      setPendingId(null);
    }
  };

  return (
    <SectionCard title="needs you" count={total || undefined}>
      {total === 0 ? (
        <div style={emptyState}>nothing waiting for you</div>
      ) : (
        actions.map((action: GatewayAction) => {
          const isBusy = pendingId === action.id;
          return (
            <div
              key={action.id}
              style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 8,
                }}
              >
                <div>
                  <div
                    style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 13,
                      fontWeight: 600,
                      color: 'var(--text)',
                      marginBottom: 2,
                    }}
                  >
                    {action.title}
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 10,
                      color: 'var(--text-muted)',
                    }}
                  >
                    {action.kind} · {action.risk_tier} · {action.source_kind}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void handleApprove(action.id)}
                    aria-label={`Approve ${action.title}`}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '4px 12px',
                      borderRadius: 4,
                      border: 'none',
                      cursor: isBusy ? 'not-allowed' : 'pointer',
                      background: 'var(--primary)',
                      color: 'var(--on-primary)',
                      opacity: isBusy ? 0.5 : 1,
                    }}
                  >
                    {isBusy ? '…' : 'approve'}
                  </button>
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void handleReject(action.id)}
                    aria-label={`Reject ${action.title}`}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '4px 12px',
                      borderRadius: 4,
                      border: '1px solid var(--border)',
                      cursor: isBusy ? 'not-allowed' : 'pointer',
                      background: 'transparent',
                      color: 'var(--text-muted)',
                      opacity: isBusy ? 0.5 : 1,
                    }}
                  >
                    reject
                  </button>
                </div>
              </div>
              {action.preview && <div style={{ ...bodyText, fontSize: 12 }}>{action.preview}</div>}
            </div>
          );
        })
      )}
      {needsJacobEntries.map((entry) => (
        <div
          key={entry.inbox_id}
          style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--text)',
              }}
            >
              needs a decision
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              {Math.round(entry.confidence * 100)}% confident
            </span>
          </div>
          {entry.text && <div style={{ ...bodyText, fontSize: 12 }}>{entry.text.slice(0, 160)}</div>}
          {entry.rationale && (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              {entry.rationale}
            </div>
          )}
          <div>
            <button
              type="button"
              onClick={() => onDecideInChat(entry)}
              style={actionButtonStyle}
            >
              decide in chat
            </button>
          </div>
        </div>
      ))}
    </SectionCard>
  );
}

// ── Open loops count ─────────────────────────────────────────────────────────

function OpenLoops() {
  const actionsQuery = useActions('proposed');
  const needsJacobQuery = useNeedsJacob();
  const loopsQuery = useLoops();
  const stateNowQuery = useStateNow();
  const runTriage = useRunInboxTriage();

  const isLoading =
    actionsQuery.isPending || needsJacobQuery.isPending || loopsQuery.isPending || stateNowQuery.isPending;
  // Actions query throws on gateway error; loops silently returns fromLiveGateway: false.
  const hasError =
    actionsQuery.isError || (loopsQuery.isFetched && loopsQuery.data?.fromLiveGateway === false);

  if (isLoading) {
    return (
      <SectionCard title="open loops">
        <div role="status" style={emptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (hasError) {
    return (
      <SectionCard title="open loops">
        <ErrorCard message="gateway offline — loop count unavailable" />
      </SectionCard>
    );
  }

  const proposedCount = actionsQuery.data?.length ?? 0;
  const needsJacobCount = needsJacobQuery.data?.entries?.length ?? 0;
  const errorLoopsCount = loopsQuery.data?.loops?.filter((l) => l.status === 'error').length ?? 0;
  const inboxSection = stateNowQuery.data?.sections.inbox;
  const untriagedCount =
    inboxSection?.ok && typeof inboxSection.untriaged_count === 'number' ? inboxSection.untriaged_count : 0;
  const total = proposedCount + needsJacobCount + errorLoopsCount + untriagedCount;

  const triageNow = untriagedCount > 0 && (
    <button
      type="button"
      disabled={runTriage.isPending}
      onClick={() => runTriage.mutate(undefined)}
      style={actionButtonStyle}
    >
      {runTriage.isPending ? '…' : 'triage now'}
    </button>
  );

  if (total === 0) {
    return (
      <SectionCard title="open loops">
        <div style={emptyState}>no open loops</div>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="open loops" count={total} action={triageNow || undefined}>
      {untriagedCount > 0 && (
        <div
          style={{
            ...itemCard,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={bodyText}>untriaged inbox</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: 14,
              color: 'var(--primary)',
            }}
          >
            {untriagedCount}
          </span>
        </div>
      )}
      {proposedCount > 0 && (
        <div
          style={{
            ...itemCard,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={bodyText}>proposed actions</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: 14,
              color: 'var(--primary)',
            }}
          >
            {proposedCount}
          </span>
        </div>
      )}
      {needsJacobCount > 0 && (
        <div
          style={{
            ...itemCard,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={bodyText}>needs jacob</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: 14,
              color: 'var(--primary)',
            }}
          >
            {needsJacobCount}
          </span>
        </div>
      )}
      {errorLoopsCount > 0 && (
        <div
          style={{
            ...itemCard,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={bodyText}>loops in error</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: 14,
              color: 'var(--error)',
            }}
          >
            {errorLoopsCount}
          </span>
        </div>
      )}
    </SectionCard>
  );
}

// ── Today (todos) ────────────────────────────────────────────────────────────

function TodayPanel({ gatewayError }: { gatewayError: string | null }) {
  // fetchGatewayTodos swallows its own errors into `[]`, so an empty list
  // here is ambiguous between "nothing today" and "gateway's down." The
  // caller passes down a sibling query's error (brief) as the tie-breaker.
  const { data: todos = [], isPending } = useTodos();

  const open = todos.filter((t) => t.status === 'pending' || t.status === 'active');

  if (isPending) {
    return (
      <SectionCard title="today">
        <div role="status" style={emptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (open.length === 0 && gatewayError) {
    return (
      <SectionCard title="today">
        <ErrorCard message={`gateway offline — ${gatewayError}`} />
      </SectionCard>
    );
  }

  return (
    <SectionCard title="today" count={open.length || undefined}>
      {open.length === 0 ? (
        <div style={emptyState}>nothing on the list</div>
      ) : (
        open.slice(0, 5).map((t) => (
          <div
            key={t.id}
            style={{ ...itemCard, display: 'flex', gap: 8, alignItems: 'flex-start' }}
          >
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 13,
                color: 'var(--primary)',
                flexShrink: 0,
                marginTop: 1,
              }}
            >
              ○
            </span>
            <span
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 13,
                color: 'var(--text)',
                lineHeight: 1.4,
              }}
            >
              {t.content}
            </span>
          </div>
        ))
      )}
      {open.length > 5 && (
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--text-muted)',
            textAlign: 'center',
          }}
        >
          +{open.length - 5} more
        </div>
      )}
    </SectionCard>
  );
}

// ── Capture ──────────────────────────────────────────────────────────────────

function CaptureSection() {
  return (
    <SectionCard title="capture">
      <CapturePanel />
    </SectionCard>
  );
}

// ── Chat drawer hint ─────────────────────────────────────────────────────────

function ChatHint() {
  return (
    <SectionCard title="chat">
      <div style={{ ...emptyState, display: 'flex', alignItems: 'center', gap: 6 }}>
        press{' '}
        <kbd
          style={{
            fontFamily: 'var(--font-mono)',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 3,
            padding: '1px 6px',
            fontSize: 11,
          }}
        >
          K
        </kbd>{' '}
        to open chat
      </div>
    </SectionCard>
  );
}

// ── Root ─────────────────────────────────────────────────────────────────────

interface Props {
  compact?: boolean;
  /** Sibling-query error (brief) used only to disambiguate Today's empty state — see TodayPanel. */
  gatewayError?: string | null;
  onDecideInChat?: (entry: GatewayTriageEntry) => void;
}

export function HomeState({ compact = false, gatewayError = null, onDecideInChat = () => {} }: Props) {
  return (
    <div
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: compact ? '16px 12px 40px' : '24px 32px 40px',
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: 20,
        alignContent: 'start',
      }}
    >
      <WhatChanged />
      <NeedsYou onDecideInChat={onDecideInChat} />
      <OpenLoops />
      <TodayPanel gatewayError={gatewayError} />
      <CaptureSection />
      <ChatHint />
    </div>
  );
}
