'use client';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState, bodyText } from '@/lib/ui';
import { CapturePanel } from '@/components/CapturePanel';
import {
  useStateChanges,
  useActions,
  useApproveAction,
  useRejectAction,
  useTodos,
  useNeedsJacob,
  useSnapshotState,
  useRunInboxTriage,
  useStateNow,
  useProjects,
  useProjectNextSteps,
  useGatewayHealth,
  useGatewayModels,
  useChatsPersistence,
  useDeadlines,
  useDeadlineSweep,
} from '@/lib/queries';
import type {
  GatewayAction,
  GatewayDeadline,
  GatewayNextStep,
  GatewayProject,
  GatewayTriageEntry,
  StateChange,
} from '@/lib/gateway';

// ── shared micro-components ──────────────────────────────────────────────────

function SectionCard({
  title,
  count,
  action,
  span,
  children,
}: {
  title: string;
  count?: number | string;
  action?: React.ReactNode;
  span?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        ...card,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        ...(span ? { gridColumn: '1 / -1' } : {}),
      }}
    >
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
  border: '1px solid var(--line)',
  cursor: 'pointer',
  background: 'var(--surface)',
  color: 'var(--ink-2)',
};

const primaryButtonStyle: React.CSSProperties = {
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

function ErrorCard({ message }: { message: string }) {
  return (
    <div
      role="alert"
      style={{ ...itemCard, color: 'var(--c-red)', fontFamily: 'var(--font-mono)', fontSize: 11 }}
    >
      {message}
    </div>
  );
}

const OFFLINE_FIX = 'gateway offline — start it with ./kitty up';

// ── Health strip ─────────────────────────────────────────────────────────────

function HealthDot({ tone, label }: { tone: 'ok' | 'warn' | 'bad'; label: string }) {
  const color =
    tone === 'ok' ? 'var(--c-green)' : tone === 'warn' ? 'var(--c-yellow)' : 'var(--c-red)';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--ink-2)',
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

function HealthStrip() {
  const health = useGatewayHealth();
  const models = useGatewayModels();
  const persistence = useChatsPersistence();
  const queryClient = useQueryClient();

  const gatewayOk = health.data?.ok === true;
  // Direct probe reported by /health — not inferred from /api/models, which
  // masks LiteLLM failures behind a fallback model list.
  const litellmOk = health.data?.litellmReachable === true;
  const storeOk = persistence.data?.ok === true;

  const retry = () => {
    queryClient.invalidateQueries({ queryKey: ['health'] });
    queryClient.invalidateQueries({ queryKey: ['models'] });
    queryClient.invalidateQueries({ queryKey: ['chats', 'persistence'] });
  };

  const loading = health.isPending || models.isPending || persistence.isPending;

  return (
    <div
      role="status"
      style={{
        ...card,
        gridColumn: '1 / -1',
        padding: '10px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 18,
        flexWrap: 'wrap',
      }}
    >
      {loading ? (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }}>
          checking gateway…
        </span>
      ) : (
        <>
          <HealthDot
            tone={gatewayOk ? 'ok' : 'bad'}
            label={gatewayOk ? 'gateway live' : OFFLINE_FIX}
          />
          <HealthDot
            tone={!gatewayOk ? 'bad' : litellmOk ? 'ok' : 'bad'}
            label={
              !gatewayOk
                ? 'routing unknown'
                : litellmOk
                  ? `routing live · ${models.data?.models.length ?? 0} models`
                  : 'litellm unreachable — ./kitty up starts it'
            }
          />
          <HealthDot
            tone={storeOk ? 'ok' : 'bad'}
            label={
              storeOk
                ? `chat store ok · ${persistence.data?.count ?? 0} saved`
                : `chat store: ${persistence.data?.error ?? 'unreachable'}`
            }
          />
        </>
      )}
      <span style={{ flex: 1 }} />
      <button type="button" onClick={retry} style={actionButtonStyle}>
        retry
      </button>
    </div>
  );
}

// ── What's next (hero) ───────────────────────────────────────────────────────

function freshestStep(steps: Array<GatewayNextStep | null | undefined>): GatewayNextStep | null {
  let best: GatewayNextStep | null = null;
  for (const s of steps) {
    if (s && (!best || s.generated_at > best.generated_at)) best = s;
  }
  return best;
}

function WhatsNext({
  onDecideInChat,
  onNavigate,
}: {
  onDecideInChat: (entry: GatewayTriageEntry) => void;
  onNavigate: (view: string) => void;
}) {
  const actionsQuery = useActions('proposed');
  const needsJacob = useNeedsJacob();
  const projectsQuery = useProjects();
  const stepQueries = useProjectNextSteps(projectsQuery.data ?? []);
  const todosQuery = useTodos();
  const approve = useApproveAction();
  const reject = useRejectAction();
  const [busy, setBusy] = useState(false);

  const isPending =
    actionsQuery.isPending || needsJacob.isPending || projectsQuery.isPending || todosQuery.isPending;

  if (isPending) {
    return (
      <SectionCard title="what's next" span>
        <div role="status" style={emptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (actionsQuery.isError || projectsQuery.isError) {
    return (
      <SectionCard title="what's next" span>
        <ErrorCard message={OFFLINE_FIX} />
      </SectionCard>
    );
  }

  const decide = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
    } catch {
      // gateway error — buttons re-enable via finally; queue refetch shows truth
    } finally {
      setBusy(false);
    }
  };

  const action: GatewayAction | undefined = (actionsQuery.data ?? [])[0];
  const entry: GatewayTriageEntry | undefined = [...(needsJacob.data?.entries ?? [])].sort(
    (a, b) => b.confidence - a.confidence,
  )[0];
  const step = freshestStep(stepQueries.map((q) => q.data));
  const project: GatewayProject | undefined = step
    ? (projectsQuery.data ?? []).find((p) => p.id === step.project_id)
    : undefined;
  const todo = (todosQuery.data ?? []).find(
    (t) => t.status === 'pending' || t.status === 'active',
  );

  return (
    <SectionCard title="what's next" span>
      {action ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{action.title}</div>
          <div style={heroMetaStyle}>
            waiting on your approval · {action.kind} · {action.risk_tier}
          </div>
          {action.preview && <div style={{ ...bodyText, fontSize: 12 }}>{action.preview}</div>}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              disabled={busy}
              onClick={() => void decide(() => approve.mutateAsync(action.id))}
              style={{ ...primaryButtonStyle, opacity: busy ? 0.5 : 1 }}
            >
              {busy ? '…' : 'approve'}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void decide(() => reject.mutateAsync(action.id))}
              style={{ ...actionButtonStyle, opacity: busy ? 0.5 : 1 }}
            >
              reject
            </button>
          </div>
        </div>
      ) : entry ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{entry.text?.slice(0, 140) || 'an inbox entry needs a decision'}</div>
          <div style={heroMetaStyle}>
            needs a decision · {Math.round(entry.confidence * 100)}% confident
          </div>
          <div>
            <button type="button" onClick={() => onDecideInChat(entry)} style={primaryButtonStyle}>
              decide in chat
            </button>
          </div>
        </div>
      ) : step ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{step.step}</div>
          <div style={heroMetaStyle}>
            {project ? `${project.name} · ` : ''}
            {step.why ? `why: ${step.why}` : 'project next step'}
          </div>
          <div>
            <button type="button" onClick={() => onNavigate('projects')} style={primaryButtonStyle}>
              open projects
            </button>
          </div>
        </div>
      ) : todo ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{todo.content}</div>
          <div style={heroMetaStyle}>top of today&apos;s list — nothing louder is waiting</div>
          <div>
            <button type="button" onClick={() => onNavigate('tasks')} style={primaryButtonStyle}>
              open tasks
            </button>
          </div>
        </div>
      ) : (
        <div style={{ ...emptyState, textAlign: 'left', padding: '12px 2px' }}>
          not enough signal yet — nothing proposed, no decisions waiting, no project next-steps,
          and today&apos;s list is empty. refresh a project in the projects tab or capture a
          thought below.
        </div>
      )}
    </SectionCard>
  );
}

const heroTextStyle: React.CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--ink)',
  lineHeight: 1.45,
};

const heroMetaStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--ink-2)',
};

// ── Active projects ──────────────────────────────────────────────────────────

function ActiveProjects({ onNavigate }: { onNavigate: (view: string) => void }) {
  const projectsQuery = useProjects();
  const stepQueries = useProjectNextSteps(projectsQuery.data ?? []);

  if (projectsQuery.isPending) {
    return (
      <SectionCard title="active projects">
        <div role="status" style={emptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (projectsQuery.isError) {
    return (
      <SectionCard title="active projects">
        <ErrorCard message={OFFLINE_FIX} />
      </SectionCard>
    );
  }

  const projects = projectsQuery.data ?? [];
  const active = projects.filter((p) => p.status === 'active');

  if (active.length === 0) {
    return (
      <SectionCard title="active projects">
        <div style={emptyState}>
          {projects.length === 0
            ? 'no projects registered — ./kitty project add <name>'
            : 'no active projects — everything is parked or done'}
        </div>
      </SectionCard>
    );
  }

  const open = (
    <button
      type="button"
      onClick={() => onNavigate('projects')}
      aria-label="Open projects"
      style={actionButtonStyle}
    >
      open
    </button>
  );

  return (
    <SectionCard title="active projects" count={active.length} action={open}>
      {active.slice(0, 4).map((p) => {
        const idx = projects.indexOf(p);
        const stepQuery = stepQueries[idx];
        const step = stepQuery?.data;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onNavigate('projects')}
            aria-label={`Open ${p.name} in projects`}
            style={{
              ...itemCard,
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              textAlign: 'left',
              width: '100%',
              cursor: 'pointer',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span
                style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--ink)',
                }}
              >
                {p.name}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
                {p.kind}
              </span>
            </div>
            <div style={{ ...bodyText, fontSize: 12 }}>
              {stepQuery?.isPending
                ? '…'
                : stepQuery?.isError
                  ? 'next step unreadable — gateway error'
                  : step
                    ? step.step
                    : 'no next step yet — refresh it in projects'}
            </div>
          </button>
        );
      })}
      {active.length > 4 && (
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--ink-2)',
            textAlign: 'center',
          }}
        >
          +{active.length - 4} more in projects
        </div>
      )}
    </SectionCard>
  );
}

// ── Deadlines (urgent paper) ─────────────────────────────────────────────────

function daysUntil(dueDate: string): number | null {
  const due = new Date(`${dueDate}T00:00:00`);
  if (Number.isNaN(due.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86_400_000);
}

function dueLabel(dueDate: string): string {
  const days = daysUntil(dueDate);
  if (days === null) return dueDate;
  if (days < 0) return `overdue ${-days}d · ${dueDate}`;
  if (days === 0) return `due today · ${dueDate}`;
  if (days === 1) return `due tomorrow · ${dueDate}`;
  return `due in ${days}d · ${dueDate}`;
}

function dueTone(dueDate: string): string {
  const days = daysUntil(dueDate);
  if (days === null) return 'var(--ink-2)';
  if (days <= 0) return 'var(--c-red)';
  if (days <= 3) return 'var(--c-yellow)';
  return 'var(--ink-2)';
}

function Deadlines() {
  const deadlines = useDeadlines('open');
  const sweep = useDeadlineSweep();

  const sweepButton = (
    <button
      type="button"
      disabled={sweep.isPending}
      onClick={() => sweep.mutate()}
      style={{ ...actionButtonStyle, opacity: sweep.isPending ? 0.5 : 1 }}
    >
      {sweep.isPending ? 'sweeping…' : 'sweep'}
    </button>
  );

  if (deadlines.isPending) {
    return (
      <SectionCard title="deadlines">
        <div role="status" style={emptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  // fetchDeadlines folds transport errors into fromLiveGateway:false so an empty
  // list can't be mistaken for the gateway being down.
  if (deadlines.data?.fromLiveGateway === false) {
    return (
      <SectionCard title="deadlines" action={sweepButton}>
        <ErrorCard message="gateway offline — deadlines unavailable" />
      </SectionCard>
    );
  }

  const open = deadlines.data?.deadlines ?? [];

  if (open.length === 0) {
    return (
      <SectionCard title="deadlines" action={sweepButton}>
        <div style={{ ...emptyState, textAlign: 'left', padding: '12px 2px' }}>
          no deadlines tracked yet — sweep scans your documents and mail for due
          dates and obligations.
          {sweep.data && sweep.data.blind_spots.length > 0 && (
            <div style={{ marginTop: 8, color: 'var(--ink-2)' }}>
              last sweep found nothing — {sweep.data.blind_spots.join(', ')}
            </div>
          )}
        </div>
      </SectionCard>
    );
  }

  const nearest = open[0];
  const rest = open.slice(1, 4);

  return (
    <SectionCard title="deadlines" count={open.length} action={sweepButton}>
      <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--ink)',
          }}
        >
          {nearest.obligation}
        </div>
        <div
          style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: dueTone(nearest.due_date) }}
        >
          {dueLabel(nearest.due_date)}
          {nearest.amount ? ` · ${nearest.currency ?? ''}${nearest.amount}` : ''}
          {nearest.confidence === 'needs_jacob' ? ' · needs your eyes' : ''}
        </div>
      </div>
      {rest.map((d: GatewayDeadline) => (
        <div
          key={d.id}
          style={{ ...itemCard, display: 'flex', justifyContent: 'space-between', gap: 8 }}
        >
          <span style={{ ...bodyText, fontSize: 12, color: 'var(--ink)' }}>{d.obligation}</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: dueTone(d.due_date),
              flexShrink: 0,
            }}
          >
            {dueLabel(d.due_date)}
          </span>
        </div>
      ))}
      {open.length > 4 && (
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--ink-2)',
            textAlign: 'center',
          }}
        >
          +{open.length - 4} more
        </div>
      )}
    </SectionCard>
  );
}

// ── What changed panel ───────────────────────────────────────────────────────

function WhatChanged() {
  const { data, isError, isPending } = useStateChanges();
  const snapshot = useSnapshotState();
  const stateNowQuery = useStateNow();
  const runTriage = useRunInboxTriage();

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

  const inboxSection = stateNowQuery.data?.sections.inbox;
  const untriagedCount =
    inboxSection?.ok && typeof inboxSection.untriaged_count === 'number'
      ? inboxSection.untriaged_count
      : 0;

  return (
    <SectionCard title="what changed" count={count || undefined} action={markPoint}>
      {note && !changes.length && !new_signals.length ? <div style={emptyState}>{note}</div> : null}
      {changes.map((c: StateChange, i: number) => (
        <div key={i} style={itemCard}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--ink-2)',
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
      {untriagedCount > 0 && (
        <div
          style={{
            ...itemCard,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={bodyText}>{untriagedCount} untriaged in inbox</span>
          <button
            type="button"
            disabled={runTriage.isPending}
            onClick={() => runTriage.mutate(undefined)}
            style={actionButtonStyle}
          >
            {runTriage.isPending ? '…' : 'triage now'}
          </button>
        </div>
      )}
      {!count && !note && !untriagedCount && (
        <div style={emptyState}>nothing new since last snapshot</div>
      )}
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
                      fontFamily: 'var(--font-body)',
                      fontSize: 13,
                      fontWeight: 600,
                      color: 'var(--ink)',
                      marginBottom: 2,
                    }}
                  >
                    {action.title}
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 10,
                      color: 'var(--ink-2)',
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
                      ...primaryButtonStyle,
                      cursor: isBusy ? 'not-allowed' : 'pointer',
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
                      border: '1px solid var(--line)',
                      cursor: isBusy ? 'not-allowed' : 'pointer',
                      background: 'transparent',
                      color: 'var(--ink-2)',
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
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--ink)',
              }}
            >
              needs a decision
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
              {Math.round(entry.confidence * 100)}% confident
            </span>
          </div>
          {entry.text && <div style={{ ...bodyText, fontSize: 12 }}>{entry.text.slice(0, 160)}</div>}
          {entry.rationale && (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
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

// ── Today (todos) ────────────────────────────────────────────────────────────

function TodayPanel({
  gatewayError,
  onNavigate,
}: {
  gatewayError: string | null;
  onNavigate: (view: string) => void;
}) {
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

  const openTasks = (
    <button
      type="button"
      onClick={() => onNavigate('tasks')}
      aria-label="Open tasks"
      style={actionButtonStyle}
    >
      open
    </button>
  );

  return (
    <SectionCard title="today" count={open.length || undefined} action={openTasks}>
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
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                color: 'var(--ink)',
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
            color: 'var(--ink-2)',
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
    <SectionCard title="capture" span>
      <CapturePanel />
    </SectionCard>
  );
}

// ── Root ─────────────────────────────────────────────────────────────────────

interface Props {
  compact?: boolean;
  /** Sibling-query error (brief) used only to disambiguate Today's empty state — see TodayPanel. */
  gatewayError?: string | null;
  onDecideInChat?: (entry: GatewayTriageEntry) => void;
  onNavigate?: (view: string) => void;
}

export function HomeState({
  compact = false,
  gatewayError = null,
  onDecideInChat = () => {},
  onNavigate = () => {},
}: Props) {
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
      <HealthStrip />
      <WhatsNext onDecideInChat={onDecideInChat} onNavigate={onNavigate} />
      <NeedsYou onDecideInChat={onDecideInChat} />
      <Deadlines />
      <ActiveProjects onNavigate={onNavigate} />
      <WhatChanged />
      <TodayPanel gatewayError={gatewayError} onNavigate={onNavigate} />
      <CaptureSection />
    </div>
  );
}
