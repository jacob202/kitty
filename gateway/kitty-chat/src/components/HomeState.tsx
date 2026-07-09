'use client';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { CapturePanel } from '@/components/CapturePanel';
import { Card, CardHeader, ItemCard, BodyText } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { StatusDot } from '@/components/ui/StatusDot';
import { EmptyState, ErrorState } from '@/components/ui/EmptyState';
import { evaluateNextAction } from '@/lib/ranking';
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
  useKnowledgeSources,
  useMagicInsights,
  useGatewayWeather,
  useDeadlines,
  useCloseDeadline,
} from '@/lib/queries';
import type {
  GatewayAction,
  GatewayNextStep,
  GatewayProject,
  GatewayTriageEntry,
  StateChange,
} from '@/lib/gateway';

const OFFLINE_FIX = 'gateway offline — start it with ./kitty up';

// ── Health strip ─────────────────────────────────────────────────────────────

function HealthStrip({ expanded }: { expanded?: boolean }) {
  const health = useGatewayHealth();
  const models = useGatewayModels();
  const persistence = useChatsPersistence();
  const queryClient = useQueryClient();

  const gatewayOk = health.data?.ok === true;
  const litellmOk = health.data?.litellmReachable === true;
  const storeOk = persistence.data?.ok === true;

  const retry = () => {
    queryClient.invalidateQueries({ queryKey: ['health'] });
    queryClient.invalidateQueries({ queryKey: ['models'] });
    queryClient.invalidateQueries({ queryKey: ['chats', 'persistence'] });
  };

  const loading = health.isPending || models.isPending || persistence.isPending;

  return (
    <Card style={{ gridColumn: '1 / -1', padding: '10px 16px', display: 'flex', alignItems: expanded ? 'flex-start' : 'center', gap: 18, flexWrap: 'wrap', flexDirection: expanded ? 'column' : 'row' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap', width: '100%' }}>
        {loading ? (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-faint)' }}>
            checking gateway…
          </span>
        ) : (
          <>
            <StatusDot
              tone={gatewayOk ? 'ok' : 'bad'}
              label={gatewayOk ? 'gateway live' : OFFLINE_FIX}
            />
            <StatusDot
              tone={!gatewayOk ? 'bad' : litellmOk ? 'ok' : 'bad'}
              label={
                !gatewayOk
                  ? 'routing unknown'
                  : litellmOk
                    ? `routing live · ${models.data?.models.length ?? 0} models`
                    : 'litellm unreachable — ./kitty up starts it'
              }
            />
            <StatusDot
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
        <Button onClick={retry}>retry</Button>
      </div>
      {expanded && !gatewayOk && (
        <ErrorState message={health.data?.error || OFFLINE_FIX} />
      )}
    </Card>
  );
}

function CockpitHeader({ rankedTitle }: { rankedTitle?: string }) {
  return (
    <section style={cockpitHeaderStyle}>
      <div style={{ display: 'grid', gap: 10, alignContent: 'center', minWidth: 0 }}>
        <div style={eyebrowStyle}>space kitty</div>
        <h1 style={cockpitTitleStyle}>Kitty</h1>
        <p style={cockpitCopyStyle}>
          Select an existing space, see the next move, then keep working without inventing fake setup work.
        </p>
        {rankedTitle && (
          <div style={missionBarStyle}>
            <span style={missionLabelStyle}>current pull</span>
            <span style={missionTextStyle}>{rankedTitle}</span>
          </div>
        )}
      </div>
      <div style={mascotFrameStyle} aria-hidden="true">
        <img
          src="/cat-assets/state-working.svg"
          alt=""
          style={{ width: 'min(190px, 34vw)', height: 'auto', display: 'block' }}
        />
      </div>
    </section>
  );
}

// ── What's next (hero) ───────────────────────────────────────────────────────

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
  const deadlinesQuery = useDeadlines('open');
  const healthQuery = useGatewayHealth();
  const approve = useApproveAction();
  const reject = useRejectAction();
  const [busy, setBusy] = useState(false);

  const isPending =
    actionsQuery.isPending || needsJacob.isPending || projectsQuery.isPending || todosQuery.isPending || deadlinesQuery.isPending || healthQuery.isPending;

  if (isPending) {
    return (
      <Card style={{ flex: '1 1 100%', gridColumn: '1 / -1' }}>
        <CardHeader title="what's next" />
        <EmptyState>loading…</EmptyState>
      </Card>
    );
  }

  if (actionsQuery.isError || projectsQuery.isError) {
    return (
      <Card style={{ flex: '1 1 100%', gridColumn: '1 / -1' }}>
        <CardHeader title="what's next" />
        <ErrorState message={OFFLINE_FIX} />
      </Card>
    );
  }

  const decide = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
    } catch {
      // gateway error
    } finally {
      setBusy(false);
    }
  };

  const rankedAction = evaluateNextAction(
    actionsQuery.data ?? [],
    needsJacob.data?.entries ?? [],
    stepQueries.map((q) => q.data).filter((s): s is GatewayNextStep => s !== null && s !== undefined),
    todosQuery.data ?? [],
    healthQuery.data ?? { ok: true, litellmReachable: true, error: null },
    deadlinesQuery.data ?? []
  );

  return (
    <Card style={{ flex: '1 1 100%', gridColumn: '1 / -1' }}>
      <CardHeader title="jacob's next move" />
      {!rankedAction ? (
        <EmptyState style={{ textAlign: 'left', padding: '12px 2px' }}>
          not enough signal yet — nothing proposed, no decisions waiting, no project next-steps,
          and today&apos;s list is empty. refresh a project in the projects tab or capture a
          thought below.
        </EmptyState>
      ) : (
        <ItemCard style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{rankedAction.title}</div>
          <div style={heroMetaStyle}>{rankedAction.reason}</div>
          {rankedAction.preview && <BodyText style={{ fontSize: 12 }}>{rankedAction.preview}</BodyText>}

          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            {rankedAction.kind === 'deadline' && (
              <Button variant="primary" onClick={() => { /* Navigate or close */ }}>
                view deadlines
              </Button>
            )}
            {rankedAction.kind === 'proposed_action' && (
              <>
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() => void decide(() => approve.mutateAsync(rankedAction.sourceId as number))}
                >
                  {busy ? '…' : 'approve'}
                </Button>
                <Button
                  disabled={busy}
                  onClick={() => void decide(() => reject.mutateAsync(rankedAction.sourceId as number))}
                >
                  reject
                </Button>
              </>
            )}
            {rankedAction.kind === 'needs_jacob' && (
              <Button variant="primary" onClick={() => onDecideInChat(rankedAction.payload as GatewayTriageEntry)}>
                decide in chat
              </Button>
            )}
            {rankedAction.kind === 'project_step' && (
              <Button variant="primary" onClick={() => onNavigate('projects')}>
                open projects
              </Button>
            )}
            {rankedAction.kind === 'todo' && (
              <Button variant="primary" onClick={() => onNavigate('tasks')}>
                open tasks
              </Button>
            )}
            {rankedAction.kind === 'gateway_error' && (
              <Button variant="primary" onClick={() => window.location.reload()}>
                refresh
              </Button>
            )}
          </div>
        </ItemCard>
      )}
    </Card>
  );
}

const heroTextStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--text)',
  lineHeight: 1.45,
};

const heroMetaStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
};

const cockpitHeaderStyle: React.CSSProperties = {
  gridColumn: '1 / -1',
  minHeight: 210,
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) auto',
  gap: 18,
  alignItems: 'center',
  padding: '28px 30px',
  border: '1px solid rgba(239,135,67,.32)',
  borderRadius: 8,
  background:
    'linear-gradient(135deg, rgba(12,17,29,.90), rgba(20,24,37,.62) 62%, rgba(26,18,28,.74))',
  boxShadow: 'var(--shadow-soft)',
  overflow: 'hidden',
  position: 'relative',
};

const eyebrowStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 0,
  color: 'var(--cat-green)',
};

const cockpitTitleStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontWeight: 800,
  fontSize: 'clamp(42px, 7vw, 76px)',
  lineHeight: 0.95,
  letterSpacing: 0,
  color: 'var(--ink)',
};

const cockpitCopyStyle: React.CSSProperties = {
  maxWidth: 560,
  fontSize: 16,
  lineHeight: 1.55,
  color: 'var(--ink-2)',
};

const mascotFrameStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  opacity: 0.88,
  filter: 'drop-shadow(0 18px 32px rgba(0,0,0,.38))',
};

const missionBarStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'auto minmax(0, 1fr)',
  gap: 10,
  alignItems: 'center',
  maxWidth: 680,
  marginTop: 4,
  padding: '10px 12px',
  border: '1px solid var(--border-dim)',
  borderRadius: 7,
  background: 'rgba(255,255,255,.035)',
};

const missionLabelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--primary)',
  fontWeight: 700,
};

const missionTextStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  color: 'var(--ink)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

// ── Spaces / projects ────────────────────────────────────────────────────────

function SpaceSelector({ onNavigate }: { onNavigate: (view: string) => void }) {
  const projectsQuery = useProjects();
  const stepQueries = useProjectNextSteps(projectsQuery.data ?? []);

  if (projectsQuery.isPending) {
    return (
      <Card>
        <CardHeader title="select space" />
        <EmptyState>loading…</EmptyState>
      </Card>
    );
  }

  if (projectsQuery.isError) {
    return (
      <Card>
        <CardHeader title="select space" />
        <ErrorState message={OFFLINE_FIX} />
      </Card>
    );
  }

  const projects = projectsQuery.data ?? [];

  if (projects.length === 0) {
    return (
      <Card>
        <CardHeader title="select space" />
        <EmptyState>
          gateway returned zero projects — refresh the gateway project store before creating anything new.
        </EmptyState>
      </Card>
    );
  }

  const open = (
    <Button onClick={() => onNavigate('projects')}>
      open
    </Button>
  );

  return (
    <Card>
      <CardHeader title="select space" count={projects.length} action={open} />
      <div style={{ display: 'grid', gap: 10 }}>
      {projects.slice(0, 5).map((p) => {
        const idx = projects.indexOf(p);
        const stepQuery = stepQueries[idx];
        const step = stepQuery?.data;
        return (
          <ItemCard
            key={p.id}
            role="button"
            onClick={() => onNavigate('projects')}
            style={{
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              borderColor: p.status === 'active' ? 'var(--primary)' : 'var(--border-dim)',
              background: p.status === 'active' ? 'var(--primary-fade)' : 'var(--surface-high)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span
                style={{
                  fontFamily: 'var(--font-ui)',
                  fontSize: 14,
                  fontWeight: 700,
                  color: 'var(--text)',
                }}
              >
                {p.name}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                {p.kind} · {p.status}
              </span>
            </div>
            <BodyText style={{ fontSize: 12 }}>
              {stepQuery?.isPending
                ? '…'
                : stepQuery?.isError
                  ? 'next step unreadable — gateway error'
                  : step
                    ? step.step
                    : 'no next step yet — refresh it in projects'}
            </BodyText>
          </ItemCard>
        );
      })}
      </div>
      {projects.length > 5 && (
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--text-muted)',
            textAlign: 'center',
          }}
        >
          +{projects.length - 5} more in projects
        </div>
      )}
    </Card>
  );
}

// ── What changed (since last look) ───────────────────────────────────────────

function WhatChanged({ onNavigate }: { onNavigate: (view: string) => void }) {
  const { data, isPending, isError } = useStateChanges();
  const stateNowQuery = useStateNow();
  const runTriage = useRunInboxTriage();
  const mark = useSnapshotState();

  if (isPending || stateNowQuery.isPending) {
    return (
      <Card>
        <CardHeader title="what changed" />
        <EmptyState>loading…</EmptyState>
      </Card>
    );
  }

  if (isError || stateNowQuery.isError) {
    return (
      <Card>
        <CardHeader title="what changed" />
        <ErrorState message="gateway offline — changes unavailable" />
      </Card>
    );
  }

  const markPoint = (
    <Button
      disabled={mark.isPending}
      onClick={() => mark.mutate(undefined)}
    >
      {mark.isPending ? '…' : 'mark point'}
    </Button>
  );

  const { changes, new_signals, note } = data;
  const count = changes.length + new_signals.length;

  const inboxSection = stateNowQuery.data?.sections.inbox;
  const untriagedCount =
    inboxSection?.ok && typeof inboxSection.untriaged_count === 'number'
      ? inboxSection.untriaged_count
      : 0;

  return (
    <Card>
      <CardHeader title="what changed" count={count || undefined} action={markPoint} />
      {note && !changes.length && !new_signals.length ? <EmptyState>{note}</EmptyState> : null}
      {changes.map((c: StateChange, i: number) => (
        <ItemCard key={i}>
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
          <BodyText>
            {String(c.before ?? '–')} → {String(c.after ?? '–')}
          </BodyText>
        </ItemCard>
      ))}
      {new_signals.length > 0 && (
        <ItemCard
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <BodyText>
            {new_signals.length} new signal{new_signals.length !== 1 ? 's' : ''} since last snapshot
          </BodyText>
        </ItemCard>
      )}
      {untriagedCount > 0 && (
        <ItemCard
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <BodyText>{untriagedCount} untriaged in inbox</BodyText>
          <Button
            disabled={runTriage.isPending}
            onClick={() => runTriage.mutate(undefined)}
          >
            {runTriage.isPending ? '…' : 'triage now'}
          </Button>
        </ItemCard>
      )}
      {!count && !note && !untriagedCount && (
        <EmptyState>nothing new since last snapshot</EmptyState>
      )}
    </Card>
  );
}

// ── Needs you (action queue) ─────────────────────────────────────────────────

function NeedsYou({ onDecideInChat }: { onDecideInChat: (entry: GatewayTriageEntry) => void }) {
  const { data: actions = [], isError, isPending } = useActions('proposed');
  const needsJacob = useNeedsJacob();
  const approve = useApproveAction();
  const reject = useRejectAction();
  const [pendingId, setPendingId] = useState<number | null>(null);

  if (isPending || needsJacob.isPending) {
    return (
      <Card>
        <CardHeader title="needs you" />
        <EmptyState>loading…</EmptyState>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader title="needs you" />
        <ErrorState message="gateway offline — action queue unavailable" />
      </Card>
    );
  }

  const needsJacobEntries = needsJacob.data?.entries ?? [];
  const total = actions.length + needsJacobEntries.length;

  const handleApprove = async (id: number) => {
    setPendingId(id);
    try {
      await approve.mutateAsync(id);
    } catch {
      // gateway error
    } finally {
      setPendingId(null);
    }
  };

  const handleReject = async (id: number) => {
    setPendingId(id);
    try {
      await reject.mutateAsync(id);
    } catch {
      // gateway error
    } finally {
      setPendingId(null);
    }
  };

  return (
    <Card>
      <CardHeader title="needs you" count={total || undefined} />
      {total === 0 ? (
        <EmptyState>nothing waiting for you</EmptyState>
      ) : (
        <>
        {actions.map((action: GatewayAction) => {
          const isBusy = pendingId === action.id;
          return (
            <ItemCard key={action.id} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>
                    {action.title}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                    {action.kind} · {action.risk_tier} · {action.source_kind}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <Button
                    variant="primary"
                    disabled={isBusy}
                    onClick={() => void handleApprove(action.id)}
                    ariaLabel={`Approve ${action.title}`}
                  >
                    {isBusy ? '…' : 'approve'}
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={isBusy}
                    onClick={() => void handleReject(action.id)}
                    ariaLabel={`Reject ${action.title}`}
                  >
                    reject
                  </Button>
                </div>
              </div>
              {action.preview && <BodyText style={{ fontSize: 12 }}>{action.preview}</BodyText>}
            </ItemCard>
          );
        })}
        {needsJacobEntries.map((entry) => (
          <ItemCard key={entry.inbox_id} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
          {entry.text && <BodyText style={{ fontSize: 12 }}>{entry.text.slice(0, 160)}</BodyText>}
          {entry.rationale && (
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              {entry.rationale}
            </div>
          )}
          <div>
            <Button
              onClick={() => onDecideInChat(entry)}
            >
              decide in chat
            </Button>
          </div>
          </ItemCard>
        ))}
        </>
      )}
    </Card>
  );
}

// ── Today (todos) ────────────────────────────────────────────────────────────

function TodayPanel({ gatewayError }: { gatewayError: string | null }) {
  const { data: todos = [], isPending } = useTodos();

  const open = todos.filter((t) => t.status === 'pending' || t.status === 'active');

  if (isPending) {
    return (
      <Card>
        <CardHeader title="today" />
        <EmptyState>loading…</EmptyState>
      </Card>
    );
  }

  if (open.length === 0 && gatewayError) {
    return (
      <Card>
        <CardHeader title="today" />
        <ErrorState message={`gateway offline — ${gatewayError}`} />
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="today" count={open.length || undefined} />
      {open.length === 0 ? (
        <EmptyState>nothing on the list</EmptyState>
      ) : (
        open.slice(0, 5).map((t) => (
          <ItemCard key={t.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--primary)', flexShrink: 0, marginTop: 1 }}>
              ○
            </span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 13, color: 'var(--text)', lineHeight: 1.4 }}>
              {t.content}
            </span>
          </ItemCard>
        ))
      )}
      {open.length > 5 && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', textAlign: 'center' }}>
          +{open.length - 5} more
        </div>
      )}
    </Card>
  );
}

// ── Deadlines ────────────────────────────────────────────────────────────────

function DeadlinesPanel() {
  const { data: deadlines = [], isPending, isError } = useDeadlines('open');
  const close = useCloseDeadline();

  if (isPending) {
    return (
      <Card>
        <CardHeader title="deadlines" />
        <EmptyState>loading…</EmptyState>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader title="deadlines" />
        <ErrorState message="gateway offline — deadlines unavailable" />
      </Card>
    );
  }

  if (deadlines.length === 0) return null;

  return (
    <Card>
      <CardHeader title="deadlines" count={deadlines.length} />
      {deadlines.map((d) => (
        <ItemCard key={d.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>
              {d.obligation}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              due: {d.due_date} {d.amount ? `· ${d.amount} ${d.currency}` : ''}
            </div>
          </div>
          <Button
            onClick={() => close.mutate(d.id)}
            disabled={close.isPending}
          >
            {close.isPending ? '…' : 'close'}
          </Button>
        </ItemCard>
      ))}
    </Card>
  );
}

// ── Phone Access ─────────────────────────────────────────────────────────────

function PhoneAccessTile() {
  const [status, setStatus] = useState<'idle' | 'checking' | 'ok' | 'fail'>('idle');

  const verify = async () => {
    setStatus('checking');
    try {
      const res = await fetch('/proxy/health');
      if (res.ok) setStatus('ok');
      else setStatus('fail');
    } catch {
      setStatus('fail');
    }
    setTimeout(() => setStatus('idle'), 3000);
  };

  return (
    <Card>
      <CardHeader title="phone access" />
      <ItemCard style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text)' }}>
          {status === 'checking' ? 'verifying…' : status === 'ok' ? 'connected to tailnet' : status === 'fail' ? 'tailnet unreachable' : 'ready for mobile'}
        </div>
        <Button onClick={verify} disabled={status === 'checking'}>
          verify now
        </Button>
      </ItemCard>
    </Card>
  );
}

// ── Capture ──────────────────────────────────────────────────────────────────

function CaptureSection() {
  return (
    <Card style={{ gridColumn: '1 / -1' }}>
      <CardHeader title="capture" />
      <CapturePanel />
    </Card>
  );
}

// ── Weather ──────────────────────────────────────────────────────────────────

function WeatherTile() {
  const { data: weatherPayload, isPending, isError } = useGatewayWeather();

  if (isPending || isError || !weatherPayload || !weatherPayload.weather) return null;
  const weather = weatherPayload.weather;

  return (
    <Card>
      <CardHeader title="sky" />
      <ItemCard style={{ display: 'flex', gap: 16, alignItems: 'center', background: 'var(--surface)', border: '2px dashed var(--border)' }}>
        <div style={{ fontSize: 44, fontFamily: 'var(--font-display)', transform: 'rotate(-4deg)', color: 'var(--text)' }}>
          {weather.temp_c ?? '--'}°
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.4 }}>
          <div>it feels {weather.description?.toLowerCase() || 'unknown'}</div>
          <div>in your area</div>
        </div>
      </ItemCard>
    </Card>
  );
}

// ── Magic Kitty & Sources ─────────────────────────────────────────────────────

function MagicKittyTile() {
  const { data: magic, isPending, isError } = useMagicInsights();

  if (isPending || isError || !magic) return null;
  const connections = magic.connections ?? [];
  if (connections.length === 0) return null;

  return (
    <Card>
      <CardHeader title="magic" count={connections.length} />
      {connections.slice(0, 3).map((c) => (
        <ItemCard key={c.insight_id} style={{ cursor: 'default' }}>
          <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--text)' }}>{c.title}</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', marginTop: 4 }}>
            {c.detail}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', marginTop: 6 }}>
            {c.source} &middot; {(c.confidence * 100).toFixed(0)}%
          </div>
        </ItemCard>
      ))}
    </Card>
  );
}

function WorkingSources({ onNavigate }: { onNavigate: (v: string) => void }) {
  const { data: sources, isPending, isError } = useKnowledgeSources();

  if (isPending || isError || !sources) return null;

  return (
    <Card>
      <CardHeader title="brain" count={sources.total_sources} />
      <ItemCard
        style={{
          cursor: 'pointer',
          border: '1px solid var(--text)',
          background: 'var(--primary-fade)',
          minWidth: 0,
          overflow: 'hidden',
        }}
        onClick={() => onNavigate('docs')}
      >
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text)', minWidth: 0 }}>
          <div style={{ fontWeight: 700 }}>{sources.total_sources} files stuffed in my head</div>
          <div style={{ marginTop: 8, color: 'var(--text-dim)' }}>
            {(sources.sources.slice(0, 3) || []).map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, padding: '2px 0', minWidth: 0 }}>
                <span>*</span>
                <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</span>
              </div>
            ))}
          </div>
        </div>
      </ItemCard>
    </Card>
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
  const healthQuery = useGatewayHealth();
  const gatewayOk = healthQuery.data?.ok === true;

  // Expanding What's Next based on the same query
  const actionsQuery = useActions('proposed');
  const needsJacob = useNeedsJacob();
  const stepQueries = useProjectNextSteps(useProjects().data ?? []);
  const todosQuery = useTodos();
  const deadlinesQuery = useDeadlines('open');

  const rankedAction = evaluateNextAction(
    actionsQuery.data ?? [],
    needsJacob.data?.entries ?? [],
    stepQueries.map((q) => q.data).filter((s): s is GatewayNextStep => s !== null && s !== undefined),
    todosQuery.data ?? [],
    healthQuery.data ?? { ok: true, litellmReachable: true, error: null },
    deadlinesQuery.data ?? []
  );

  return (
    <div
      className="kitty-cockpit"
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: compact ? '16px 12px 120px' : '28px 32px 44px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: compact ? 14 : 18,
        alignContent: 'flex-start',
        alignItems: 'flex-start',
        minHeight: '100%',
        background:
          'radial-gradient(circle at 20% 16%, rgba(116,168,255,.13) 0 1px, transparent 1.5px), radial-gradient(circle at 80% 18%, rgba(240,198,106,.22) 0 1px, transparent 1.5px), radial-gradient(circle at 62% 62%, rgba(109,220,192,.12) 0 1px, transparent 1.5px), linear-gradient(135deg, rgba(6,10,20,.96), rgba(9,13,24,.92) 48%, rgba(15,10,18,.96))',
        backgroundSize: '160px 160px, 220px 220px, 180px 180px, 100% 100%',
      }}
    >
      <CockpitHeader rankedTitle={rankedAction?.title} />
      <HealthStrip expanded={!gatewayOk} />
      <WhatsNext onDecideInChat={onDecideInChat} onNavigate={onNavigate} />
      <DeadlinesPanel />
      <SpaceSelector onNavigate={onNavigate} />
      <NeedsYou onDecideInChat={onDecideInChat} />
      <TodayPanel gatewayError={gatewayError} />
      <WhatChanged onNavigate={onNavigate} />
      <WeatherTile />
      <PhoneAccessTile />
      <MagicKittyTile />
      <WorkingSources onNavigate={onNavigate} />
      <CaptureSection />
    </div>
  );
}
