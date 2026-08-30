'use client';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { card, cardHeader, cardTitle, cardMeta, itemCard, emptyState, bodyText } from '@/lib/ui';
import { CapturePanel } from '@/components/CapturePanel';
import { BuilderGlance } from '@/components/BuilderSurface';
import { InsightReturnCard } from '@/components/InsightReturnCard';
import { useDashboardConfig } from '@/hooks/useDashboardConfig';
import { describeFailure } from '@/lib/failure-copy';
import { projectNextStepCopy } from '@/lib/project-copy';
import {
  useStateChanges,
  useActions,
  useApproveAction,
  useExecuteAction,
  useRejectAction,
  useTodos,
  useNeedsJacob,
  useSnapshotState,
  useRunInboxTriage,
  useStateNow,
  useProjects,
  useProjectNextSteps,
  useWhatsNextSteps,
  useGatewayHealth,
  useHealthSurface,
  useGatewayModels,
  useChatsPersistence,
  useSessionContext,
  useDeadlines,
  useDeadlineSweep,
  useTailnet,
  useRepairs,
  useExecuteRepair,
  useExpertList,
  useSignals,
  useGatewayWeather,
} from '@/lib/queries';
import type {
  GatewayAction,
  GatewayDeadline,
  GatewayNextStep,
  GatewayProject,
  GatewayTriageEntry,
  StateChange,
  RepairItem,
  ExpertProfile,
} from '@/lib/gateway';

// ── shared micro-components ──────────────────────────────────────────────────

function friendlyLabel(raw: string): string {
  if (!raw) return raw;
  const lower = raw.toLowerCase().replace(/_/g, ' ');

  if (lower.includes('psychological profile')) return 'Something to carry forward';
  if (lower.includes('mental state')) return 'Last useful thought';
  if (lower.includes('surveillance')) return 'Quiet memory';
  if (lower.includes('diagnosis')) return 'Decision kept';
  if (lower.includes('user traits')) return 'Continue';

  return raw;
}

// Tiny crude white-doodle Kitty (see public/cat-assets/kid-cat.svg) used as
// small dashboard decoration under the cosmic theme. Intentionally rough.
function KidCatDoodle({ size = 36, opacity = 0.5 }: { size?: number; opacity?: number }) {
  return (
    <svg
      viewBox="0 0 280 210"
      width={size}
      height={size * (210 / 280)}
      style={{ opacity, display: 'block', pointerEvents: 'none' }}
      aria-hidden
    >
      <g
        stroke="currentColor"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <ellipse cx="168" cy="128" rx="62" ry="46" />
        <circle cx="80" cy="102" r="44" />
        <path d="M54 66 L44 24 L88 58" />
        <path d="M98 58 L118 24 L122 64" />
        <circle cx="64" cy="96" r="5" fill="currentColor" stroke="none" />
        <path d="M38 104 L52 100 L49 112 Z" />
        <path d="M44 113 Q58 126 74 116" />
        <path d="M36 100 Q20 96 8 102 M38 114 Q22 116 10 124" />
        <path d="M120 168 q-4 18 6 20 M152 172 q-2 18 7 20 M188 170 q0 18 8 19 M214 160 q5 16 12 17" />
        <path d="M226 122 Q262 112 256 70 Q254 48 236 58" />
      </g>
    </svg>
  );
}


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
        background: 'var(--color-surface)',
        border: '1px solid var(--color-separator)',
        borderRadius: 'var(--r-surface)',
        boxShadow: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        ...(span ? { gridColumn: '1 / -1' } : {}),
      }}
    >
      <div style={{ ...cardHeader, borderBottom: '1px solid var(--color-separator)', paddingBottom: 10 }}>
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
  fontFamily: 'var(--font-body)',
  fontSize: 11,
  fontWeight: 650,
  padding: '5px 9px',
  borderRadius: 8,
  border: '1px solid var(--color-separator)',
  cursor: 'pointer',
  background: 'var(--color-surface)',
  color: 'var(--color-text-secondary)',
};

const primaryButtonStyle: React.CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  fontWeight: 650,
  padding: '7px 12px',
  borderRadius: 10,
  border: 'none',
  cursor: 'pointer',
  background: 'var(--color-accent)',
  color: 'var(--on-accent)',
};

const homeEmptyState: React.CSSProperties = {
  ...emptyState,
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  lineHeight: 1.5,
  color: 'var(--color-text-muted)',
};

function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      style={{ ...itemCard, display: 'flex', alignItems: 'center', gap: 10, color: 'var(--c-red)', fontFamily: 'var(--font-mono)', fontSize: 11 }}
    >
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} style={actionButtonStyle} aria-label="retry loading">
          retry
        </button>
      )}
    </div>
  );
}

const OFFLINE_FIX = 'Kitty is not connected — check if Kitty is running';

// ── Repairs card ──────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  ok: 'var(--c-green)',
  warn: 'var(--c-yellow)',
  error: 'var(--c-red)',
}

function repairTitle(title: string, detail?: string | null): string {
  const raw = `${title} ${detail ?? ''}`
  if (/transition history/i.test(raw)) return 'Builder activity history needs attention'
  if (/partial packet records?/i.test(raw)) return 'Some Builder work is incomplete'
  return title
}

function repairDetail(title: string, detail?: string | null): string {
  const raw = `${title} ${detail ?? ''}`
  if (/transition history|partial packet records?/i.test(raw)) return ''
  return detail ?? ''
}

function RepairsCard() {
  const repairs = useRepairs()
  const execRepair = useExecuteRepair()
  const queryClient = useQueryClient()

  if (repairs.isPending) {
    return (
      <SectionCard title="system">
        <div role="status" style={homeEmptyState}>
          checking…
        </div>
      </SectionCard>
    )
  }

  if (repairs.isError || !repairs.data) {
    return (
      <SectionCard title="system">
        <ErrorCard message="unavailable" />
      </SectionCard>
    )
  }

  const issues = repairs.data.repairs.filter((r) => r.severity !== 'ok')

  // Zero checks run is not a clean bill of health — it means nothing was
  // measured. Saying "everything looks healthy" there sat directly above a
  // "gateway is not reachable" banner and made the whole panel untrustworthy.
  if (issues.length === 0 && repairs.data.checks_run === 0) {
    return (
      <SectionCard title="system">
        <div role="status" style={homeEmptyState}>
          nothing was checked — Kitty could not complete its health checks
        </div>
      </SectionCard>
    )
  }

  if (issues.length === 0) {
    return (
      <SectionCard title="system">
        <div style={{ ...homeEmptyState, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div>everything looks healthy</div>
          <div style={{ fontSize: 10 }}>{repairs.data.checks_run} checks passed — all services are responding</div>
        </div>
      </SectionCard>
    )
  }

  return (
    <SectionCard title="system" count={issues.length}>
      {issues.map((item) => (
        <div key={item.id} style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: SEVERITY_COLORS[item.severity] ?? 'var(--ink-2)',
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--ink)',
                flex: 1,
              }}
            >
              {repairTitle(item.title, item.detail)}
            </span>
          </div>
          {repairDetail(item.title, item.detail) && (
            <div style={{ ...bodyText, fontSize: 11, color: 'var(--ink-2)', paddingLeft: 14 }}>
              {repairDetail(item.title, item.detail)}
            </div>
          )}
          {item.fix && (
            <div style={{ display: 'flex', gap: 6, paddingLeft: 14 }}>
              <button
                type="button"
                disabled={execRepair.isPending}
                onClick={() =>
                  execRepair.mutate({
                    repairId: item.id,
                    actionKind: item.fix!.action_kind,
                    checkName: item.fix!.check_name,
                  })
                }
                style={actionButtonStyle}
              >
                {execRepair.isPending ? '…' : item.fix.label}
              </button>
              <button
                type="button"
                disabled={execRepair.isPending}
                onClick={() =>
                  execRepair.mutate({
                    repairId: item.id,
                    actionKind: 'repair.dismiss',
                    checkName: item.id,
                  })
                }
                style={{ ...actionButtonStyle, color: 'var(--ink-2)', opacity: 0.7 }}
              >
                dismiss
              </button>
            </div>
          )}
        </div>
      ))}
      <div style={{ paddingTop: 4 }}>
        <button
          type="button"
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['repairs'] })
          }}
          style={{ ...actionButtonStyle, width: '100%', textAlign: 'center' }}
        >
          refresh
        </button>
      </div>
    </SectionCard>
  )
}

// ── Signals card (reuses Repairs shape) ──────────────────────────────────────

function SignalsCard() {
  const signals = useSignals()
  const execRepair = useExecuteRepair()

  if (signals.isPending || !signals.data) return null

  const issues = signals.data.repairs.filter((r) => r.severity !== 'ok')

  if (issues.length === 0) return null

  return (
    <SectionCard title="signals" count={issues.length}>
      {issues.map((item) => (
        <div key={item.id} style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: SEVERITY_COLORS[item.severity] ?? 'var(--ink-2)',
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--ink)',
                flex: 1,
              }}
            >
              {item.title}
            </span>
          </div>
          {item.detail && (
            <div style={{ ...bodyText, fontSize: 11, color: 'var(--ink-2)', paddingLeft: 14 }}>
              {item.detail}
            </div>
          )}
          {item.fix && (
            <div style={{ display: 'flex', gap: 6, paddingLeft: 14 }}>
              <button
                type="button"
                disabled={execRepair.isPending}
                onClick={() =>
                  execRepair.mutate({
                    repairId: item.id,
                    actionKind: item.fix!.action_kind,
                    checkName: item.fix!.check_name,
                  })
                }
                style={actionButtonStyle}
              >
                {execRepair.isPending ? '…' : item.fix.label}
              </button>
            </div>
          )}
        </div>
      ))}
    </SectionCard>
  )
}

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
        fontFamily: 'var(--font-body)',
        fontSize: 12,
        color: 'var(--color-text-secondary)',
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
  const repairs = useRepairs();
  const queryClient = useQueryClient();

  const gatewayOk = health.data?.ok === true;
  // Direct probe reported by /health — not inferred from /api/models, which
  // masks LiteLLM failures behind a fallback model list.
  const litellmOk = health.data?.litellmReachable === true;
  const modelsLive = models.data?.fromLiveGateway === true;
  const storeOk = persistence.data?.ok === true;
  const repairIssues = repairs.data?.repairs.filter((repair) => repair.severity !== 'ok').length ?? 0;
  const repairChecksUnknown = !repairs.isPending && (repairs.isError || !repairs.data || repairs.data.checks_run === 0);
  const kittyNeedsAttention = !gatewayOk || repairIssues > 0 || repairChecksUnknown;

  const retry = () => {
    queryClient.invalidateQueries({ queryKey: ['health'] });
    queryClient.invalidateQueries({ queryKey: ['models'] });
    queryClient.invalidateQueries({ queryKey: ['chats', 'persistence'] });
    queryClient.invalidateQueries({ queryKey: ['repairs'] });
  };

  const loading = health.isPending || models.isPending || persistence.isPending || repairs.isPending;

  return (
    <div
      role="status"
      style={{
        ...card,
        background: 'var(--color-surface)',
        border: '1px solid var(--color-separator)',
        borderRadius: 14,
        boxShadow: 'none',
        gridColumn: '1 / -1',
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 18,
        flexWrap: 'wrap',
      }}
    >
      {loading ? (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }}>
          checking Kitty connection — status lands here in a sec…
        </span>
      ) : (
        <>
          <HealthDot
            tone={kittyNeedsAttention ? 'bad' : 'ok'}
            label={
              !gatewayOk
                ? OFFLINE_FIX
                : repairIssues > 0
                  ? `Kitty needs attention · ${repairIssues} issue${repairIssues === 1 ? '' : 's'}`
                  : repairChecksUnknown
                    ? 'Kitty checks need attention'
                    : 'Kitty is connected'
            }
          />
          <HealthDot
            tone={!gatewayOk || !litellmOk ? 'bad' : modelsLive ? 'ok' : 'warn'}
            label={
              !gatewayOk
                ? 'models unknown'
                : !litellmOk
                  ? 'models are unavailable'
                  : modelsLive
                    ? `models ready · ${models.data?.models.length ?? 0}`
                    : 'model list unavailable'
            }
          />
          <HealthDot
            tone={storeOk ? 'ok' : 'bad'}
            label={
              storeOk
                ? `saved chats · ${persistence.data?.count ?? 0}`
                : `saved chats unavailable${persistence.data?.error ? ` · ${describeFailure(persistence.data.error)}` : ''}`
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

// ── Health surface (full-stack projection) ───────────────────────────────────

const HEALTH_TONES: Record<string, 'ok' | 'warn' | 'bad'> = {
  available: 'ok',
  degraded: 'warn',
  stale: 'warn',
  unavailable: 'bad',
  unknown: 'warn',
};

const HEALTH_LABELS: Record<string, string> = {
  gateway: 'Kitty connection',
  database: 'saved data',
  memory: 'memory',
  automation_supervisor: 'background tasks',
  cron: 'scheduled tasks',
  telegram: 'messages',
  image_lab: 'image lab',
  image_providers: 'image creation',
  image_queue: 'image jobs',
  ollama: 'local AI',
  pending_grants: 'pending approvals',
};

/** Strip internal naming (env vars, routes, hostnames) that must never reach the user. */
function sanitizeReason(raw: string): string {
  return raw
    .replace(/\b[A-Z][A-Z_0-9]{2,}\b/g, '')        // ENV_VAR style names
    .replace(/\/[a-z][\w/.\-]*/gi, '')               // /api/routes, /health/surface etc.
    .replace(/localhost:\d+/gi, '')                    // localhost:4110
    .replace(/\b\d{3,5}\b/g, '')                      // bare port/error numbers
    .replace(/[,;:\-–]+/g, ' ')                       // leftover punctuation
    .replace(/\s{2,}/g, ' ')                          // collapse whitespace
    .trim()
}

function healthReasonCopy(status: string, reason?: string): string {
  const clean = reason ? sanitizeReason(reason) : '';
  if (status === 'unavailable') {
    return clean || 'This part of Kitty is unavailable right now. Refresh health to check again.';
  }
  if (status === 'degraded') {
    return clean || 'This part of Kitty is having trouble right now. Refresh health to check again.';
  }
  if (status === 'stale') {
    return 'This status is out of date. Refresh health to check again.';
  }
  return 'No additional issue details are available.';
}

// One operator-facing surface for "is Kitty working, and if not exactly what
// is wrong". Rows for every domain, a degraded section that expands the reason
// on click, and a "still functional" section so a partial outage is honest.
function HealthSurfaceCard() {
  const surface = useHealthSurface();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  if (surface.isPending) {
    return (
      <SectionCard title="health" span>
        <div role="status" style={homeEmptyState}>
          checking…
        </div>
      </SectionCard>
    );
  }

  if (surface.isError || !surface.data || !surface.data.ok) {
    return (
      <SectionCard title="health" span>
        <ErrorCard
          message={describeFailure(surface.error ?? surface.data?.error)}
          onRetry={() => surface.refetch()}
        />
      </SectionCard>
    );
  }

  const { overall, domains, degraded, still_functional: stillFunctional, pending_grants: pendingGrants } = surface.data;
  const domainBy = new Map(domains.map((d) => [d.name, d]));

  return (
    <SectionCard
      title="health"
      count={overall ?? '—'}
      span
      action={
        <button
          type="button"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['health-surface'] })}
          style={actionButtonStyle}
        >
          refresh
        </button>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
        {domains.map((domain) => (
          <div key={domain.name} style={{ ...itemCard, display: 'flex', alignItems: 'center', gap: 8 }}>
            <HealthDot tone={HEALTH_TONES[domain.status] ?? 'warn'} label={HEALTH_LABELS[domain.name] ?? domain.name} />
          </div>
        ))}
      </div>

      {degraded.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--c-red)' }}>
            degraded
          </div>
          {degraded.map((name) => {
            const domain = domainBy.get(name);
            const open = expanded === name;
            return (
              <div key={name} style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <button
                  type="button"
                  onClick={() => setExpanded(open ? null : name)}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', width: '100%' }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)', flex: 1 }}>
                    {HEALTH_LABELS[name] ?? name}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', opacity: 0.7 }}>
                    {open ? 'collapse' : 'explain'}
                  </span>
                </button>
                {open && (
                  <div style={{ ...bodyText, fontSize: 11, color: 'var(--ink-2)', paddingLeft: 0 }}>
                    {healthReasonCopy(domain?.status ?? 'unknown', domain?.reason)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {stillFunctional.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--c-green)' }}>
            still functional
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {stillFunctional.map((name) => (
              <HealthDot key={name} tone="ok" label={HEALTH_LABELS[name] ?? name} />
            ))}
          </div>
        </div>
      )}

      {pendingGrants > 0 && (
        <div style={{ ...bodyText, fontSize: 11, color: 'var(--ink-2)' }}>
          {pendingGrants} pending approval{pendingGrants === 1 ? '' : 's'} waiting on you
        </div>
      )}
    </SectionCard>
  );
}

// ── Action approval: approve -> execute -> terminal outcome (C7-F08) ────────
// Approving a T2 action only moves it proposed -> approved; it never runs on
// its own. Without this second call the action sits "approved" forever and
// the person who approved it never learns whether it actually happened.

type ActionOutcome = { title: string; ok: boolean; message: string };

async function approveAndExecuteAction(
  action: GatewayAction,
  approve: { mutateAsync: (id: number) => Promise<GatewayAction> },
  execute: { mutateAsync: (id: number) => Promise<GatewayAction> },
): Promise<ActionOutcome> {
  await approve.mutateAsync(action.id);
  try {
    const executed = await execute.mutateAsync(action.id);
    return {
      title: action.title,
      ok: executed.status === 'executed',
      message: executed.result || (executed.status === 'executed' ? 'done' : `status: ${executed.status}`),
    };
  } catch (err) {
    return {
      title: action.title,
      ok: false,
      message: err instanceof Error ? err.message : 'could not run this action',
    };
  }
}

// ── What's next (hero) ───────────────────────────────────────────────────────

// Local time, not UTC — this only ever renders client-side (Home is behind
// the app's post-mount gate), so there's no SSR/hydration mismatch to guard.
function greeting(hour: number): string {
  if (hour < 12) return 'good morning';
  if (hour < 17) return 'good afternoon';
  return 'good evening';
}

function WhatsNext({
  onDecideInChat,
  onNavigate,
  preferredName = '',
}: {
  onDecideInChat: (entry: GatewayTriageEntry) => void;
  onNavigate: (view: string) => void;
  preferredName?: string;
}) {
  const actionsQuery = useActions('proposed');
  const needsJacob = useNeedsJacob();
  const projectsQuery = useProjects();
  const stepQueries = useWhatsNextSteps();
  const todosQuery = useTodos();
  const approve = useApproveAction();
  const execute = useExecuteAction();
  const reject = useRejectAction();
  const sessionContext = useSessionContext();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);

  // ── Error checks first ──
  // These run before the loading guard so that a known failure (observed:
  // stale gateway 404'd /session/context) renders immediately with a retry
  // control instead of staying stuck on "loading…" while other queries settle.

  if (sessionContext.isError) {
    const retry = () => queryClient.invalidateQueries({ queryKey: ['session', 'context'] });
    return (
      <SectionCard title="what's next" span>
        <ErrorCard message={describeFailure(sessionContext.error)} onRetry={retry} />
      </SectionCard>
    );
  }

  if (actionsQuery.isError || projectsQuery.isError) {
    const failed = actionsQuery.isError ? actionsQuery : projectsQuery;
    return (
      <SectionCard title="what's next" span>
        <ErrorCard message={describeFailure(failed.error)} onRetry={() => failed.refetch()} />
      </SectionCard>
    );
  }

  if (todosQuery.isError || needsJacob.isError) {
    const failed = todosQuery.isError ? todosQuery : needsJacob;
    const retryKey = todosQuery.isError ? ['todos'] : ['inbox', 'needs_jacob'];
    const retry = () => queryClient.invalidateQueries({ queryKey: retryKey });
    return (
      <SectionCard title="what's next" span>
        <ErrorCard message={describeFailure(failed.error)} onRetry={retry} />
      </SectionCard>
    );
  }

  // ── Loading guard ──
  // Only show "loading…" when no query has already failed (all errors handled above).
  const isPending =
    actionsQuery.isPending || needsJacob.isPending || projectsQuery.isPending || todosQuery.isPending || sessionContext.isPending;

  if (isPending) {
    return (
      <SectionCard title="what's next" span>
        <div role="status" style={homeEmptyState}>
          loading…
        </div>
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

  const handleApprove = async (targetAction: GatewayAction) => {
    setBusy(true);
    try {
      setOutcome(await approveAndExecuteAction(targetAction, approve, execute));
    } catch {
      // approve itself failed — button re-enables via finally, nothing ran
    } finally {
      setBusy(false);
    }
  };

  const action: GatewayAction | undefined = (actionsQuery.data ?? [])[0];
  const entry: GatewayTriageEntry | undefined = [...(needsJacob.data?.entries ?? [])].sort(
    (a, b) => b.confidence - a.confidence,
  )[0];
  const step = stepQueries.data?.[0] ?? null;
  const project: GatewayProject | undefined = step
    ? (projectsQuery.data ?? []).find((p) => p.id === step.project_id)
    : undefined;
  const displayStep = step && project ? projectNextStepCopy(project, step) : step;
  const todo = (todosQuery.data ?? []).find(
    (t) => t.status === 'pending' || t.status === 'active',
  );

  return (
    <SectionCard title="what's next" span>
      {outcome && (
        <div
          role="status"
          style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}
        >
          <div style={heroMetaStyle}>
            {outcome.ok ? 'done' : 'did not complete'} · {outcome.title}
          </div>
          <div style={{ ...bodyText, fontSize: 12 }}>{outcome.message}</div>
          <div>
            <button
              type="button"
              onClick={() => setOutcome(null)}
              style={{ ...actionButtonStyle, color: 'var(--ink-2)', opacity: 0.7 }}
            >
              dismiss
            </button>
          </div>
        </div>
      )}
      {action ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{action.title}</div>
          <div style={heroMetaStyle}>
            waiting on your approval · {friendlyLabel(action.kind)} · {action.risk_tier}
          </div>
          {action.preview && <div style={{ ...bodyText, fontSize: 12 }}>{action.preview}</div>}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleApprove(action)}
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
            <button type="button" onClick={() => onDecideInChat(entry)} style={primaryButtonStyle} aria-label="decide in chat">
              decide in chat
            </button>
          </div>
        </div>
      ) : displayStep ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{displayStep.step}</div>
          <div style={heroMetaStyle}>
            {project ? `${project.name} · ` : ''}
            {displayStep.why ? `why: ${displayStep.why}` : 'project next step'}
          </div>
          <div>
            <button type="button" onClick={() => onNavigate('projects')} style={primaryButtonStyle} aria-label="open projects">
              open projects
            </button>
          </div>
        </div>
      ) : todo ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>{todo.content}</div>
          <div style={heroMetaStyle}>top of today&apos;s list — nothing louder is waiting</div>
          <div>
            <button type="button" onClick={() => onNavigate('tasks')} style={primaryButtonStyle} aria-label="open tasks">
              open tasks
            </button>
          </div>
        </div>
      ) : sessionContext.data?.last_session_topic ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>last session: {sessionContext.data.last_session_topic}</div>
          <div style={heroMetaStyle}>
            {sessionContext.data.next_actions[0]
              ? `next: ${sessionContext.data.next_actions[0]}`
              : `${sessionContext.data.open_threads.length} saved session thread${sessionContext.data.open_threads.length === 1 ? '' : 's'}`}
          </div>
        </div>
      ) : sessionContext.data?.open_threads.length ? (
        <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={heroTextStyle}>open threads</div>
          <div style={heroMetaStyle}>{sessionContext.data.open_threads.join(' · ')}</div>
        </div>
      ) : (
        <div style={{ ...homeEmptyState, textAlign: 'left', padding: '12px 2px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <span aria-hidden style={{ color: 'var(--cat-ginger)', flexShrink: 0, pointerEvents: 'none' }}>
            <KidCatDoodle size={40} opacity={0.7} />
          </span>
      <span style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>
            {greeting(new Date().getHours())}{preferredName ? `, ${preferredName}` : ''} — not enough signal yet
          </span>
        <span>
              nothing proposed, no decisions waiting, no project next-steps, and today's list
              is empty. refresh a project in the projects tab or capture a thought below.
            </span>
          </span>
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
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  lineHeight: 1.45,
  color: 'var(--color-text-muted)',
};

// ── Active projects ──────────────────────────────────────────────────────────

function ActiveProjects({ onNavigate }: { onNavigate: (view: string) => void }) {
  const projectsQuery = useProjects();
  const stepQueries = useProjectNextSteps(projectsQuery.data ?? []);

  if (projectsQuery.isPending) {
    return (
      <SectionCard title="active projects">
        <div role="status" style={homeEmptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (projectsQuery.isError) {
    return (
      <SectionCard title="active projects">
        <ErrorCard message={describeFailure(projectsQuery.error)} onRetry={() => projectsQuery.refetch()} />
      </SectionCard>
    );
  }

  const projects = projectsQuery.data ?? [];
  const active = projects.filter((p) => p.status === 'active');

  if (active.length === 0) {
    return (
      <SectionCard title="active projects">
        <div style={homeEmptyState}>
          {projects.length === 0
            ? 'no projects registered — add one from the projects view'
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
        const displayStep = step ? projectNextStepCopy(p, step) : null;
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
                  ? 'next step unavailable — try again from Projects'
                  : displayStep
                    ? displayStep.step
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

// ── Experts shelf ────────────────────────────────────────────────────────────

function ExpertStrip({ onExpertClick }: { onExpertClick: (expert: ExpertProfile) => void }) {
  const expertList = useExpertList()
  const experts = expertList.data ?? []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? experts : experts.slice(0, 2)

  if (expertList.isPending) return null
  if (experts.length === 0) return null

  return (
    <SectionCard title="experts" count={experts.length}>
      {visible.map((expert) => (
        <button
          key={expert.id}
          type="button"
          onClick={() => onExpertClick(expert)}
          style={{
            ...itemCard,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            textAlign: 'left',
            width: '100%',
            cursor: 'pointer',
            background: 'transparent',
            border: '1px solid transparent',
            borderRadius: 6,
            padding: '8px 10px',
            transition: 'border-color 150ms ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--line)' }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'transparent' }}
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
              {expert.label}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
              {expert.book_count} books
            </span>
          </div>
          <div style={{ ...bodyText, fontSize: 12 }}>
            {expert.sample_title}
            {expert.tags.length > 0 && ` · ${expert.tags.slice(0, 2).join(', ')}`}
          </div>
        </button>
      ))}
      {experts.length > 2 && (
        <div style={{ textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            style={actionButtonStyle}
          >
            {expanded ? 'show less' : `show all ${experts.length} experts`}
          </button>
        </div>
      )}
    </SectionCard>
  )
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

function PhoneAccessCard() {
  const tailnet = useTailnet();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  if (tailnet.isPending) {
    return (
      <SectionCard title="phone access">
        <div role="status" style={homeEmptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (!tailnet.data?.ok || !tailnet.data.uiUrl) {
    return (
      <SectionCard title="phone access">
        <div style={{ ...homeEmptyState, textAlign: 'left', padding: '12px 2px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>Phone access needs its secure connection app running on this Mac.</div>
          <div style={{ ...bodyText, fontSize: 11 }}>
            Open the phone access app, then try Kitty from your phone again.
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              onClick={() => window.open('tailscale://', '_blank')}
              style={actionButtonStyle}
            >
              open phone access
            </button>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              style={{ ...actionButtonStyle, color: 'var(--ink-2)', opacity: 0.7 }}
            >
              dismiss
            </button>
          </div>
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="phone access">
      <div style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>
          reachable from your iPhone
        </div>
        <div style={{ ...bodyText, fontFamily: 'var(--font-mono)', color: 'var(--primary)' }}>
          {tailnet.data.uiUrl}
        </div>
        <div style={{ display: 'flex', gap: 6, paddingTop: 4 }}>
          <button
            type="button"
            onClick={() => setDismissed(true)}
            style={{ ...actionButtonStyle, color: 'var(--ink-2)', opacity: 0.7 }}
          >
            dismiss
          </button>
        </div>
      </div>
    </SectionCard>
  );
}

function Deadlines() {
  const deadlines = useDeadlines('open');
  const sweep = useDeadlineSweep();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

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
        <div role="status" style={homeEmptyState}>
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
        <ErrorCard message={describeFailure(deadlines.data?.error)} onRetry={() => deadlines.refetch()} />
      </SectionCard>
    );
  }

  const open = deadlines.data?.deadlines ?? [];

  if (open.length === 0) {
    return (
      <SectionCard title="deadlines" action={sweepButton}>
        <div style={{ ...homeEmptyState, textAlign: 'left', padding: '12px 2px' }}>
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
      aria-label="Mark current time as baseline snapshot"
      style={actionButtonStyle}
    >
      {snapshot.isPending ? '…' : 'mark point'}
    </button>
  );

  if (isPending) {
    return (
      <SectionCard title="what changed">
        <div role="status" style={{ ...homeEmptyState }}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (isError || !data) {
    return (
      <SectionCard title="what changed">
        <ErrorCard message="unavailable" />
      </SectionCard>
    );
  }

  const { baseline_ts, changes, new_signals } = data;
  const count = changes.length + new_signals.length;

  const inboxSection = stateNowQuery.data?.sections.inbox;
  const untriagedCount =
    inboxSection?.ok && typeof inboxSection.untriaged_count === 'number'
      ? inboxSection.untriaged_count
      : 0;

  return (
    <SectionCard title="what changed" count={count || undefined} action={markPoint}>
      {baseline_ts === null && !changes.length && !new_signals.length ? (
        <div style={homeEmptyState}>no comparison point yet — mark one to start tracking changes</div>
      ) : null}
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
            {friendlyLabel(c.section)}
            {c.field ? ` · ${friendlyLabel(c.field)}` : ''}
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
      {!count && baseline_ts !== null && !untriagedCount && (
        <div style={{ ...homeEmptyState, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div>nothing new since last snapshot</div>
          <div style={{ fontSize: 10 }}>tap mark point anytime to set a fresh baseline</div>
        </div>
      )}
    </SectionCard>
  );
}

// ── Needs you (action queue) ─────────────────────────────────────────────────

function NeedsYou({ onDecideInChat }: { onDecideInChat: (entry: GatewayTriageEntry) => void }) {
  const { data: actions = [], isError, isPending, error, refetch } = useActions('proposed');
  const needsJacob = useNeedsJacob();
  const approve = useApproveAction();
  const execute = useExecuteAction();
  const reject = useRejectAction();
  // Track which action is in-flight to disable its buttons and prevent races.
  const [pendingId, setPendingId] = useState<number | null>(null);
  // Approving moves an action out of `actions` (no longer 'proposed'), so its
  // terminal outcome has to live here, not in the query result, or it would
  // vanish the instant it's most useful to see.
  const [outcomes, setOutcomes] = useState<Record<number, ActionOutcome>>({});

  if (isPending || needsJacob.isPending) {
    return (
      <SectionCard title="needs you">
        <div role="status" style={homeEmptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (isError) {
    return (
      <SectionCard title="needs you">
        <ErrorCard message={describeFailure(error)} onRetry={() => refetch()} />
      </SectionCard>
    );
  }

  const needsJacobEntries = needsJacob.data?.entries ?? [];
  const total = actions.length + needsJacobEntries.length;

  const handleApprove = async (action: GatewayAction) => {
    setPendingId(action.id);
    try {
      const result = await approveAndExecuteAction(action, approve, execute);
      setOutcomes((current) => ({ ...current, [action.id]: result }));
    } catch {
      // approve itself failed — button re-enables via finally, nothing ran
    } finally {
      setPendingId(null);
    }
  };

  const dismissOutcome = (id: number) => {
    setOutcomes((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
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
      {Object.entries(outcomes).map(([idStr, result]) => (
        <div
          key={idStr}
          role="status"
          style={{ ...itemCard, display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          <div
            style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}
          >
            {result.ok ? 'done' : 'did not complete'} · {result.title}
          </div>
          <div style={{ ...bodyText, fontSize: 12 }}>{result.message}</div>
          <div>
            <button
              type="button"
              onClick={() => dismissOutcome(Number(idStr))}
              style={{ ...actionButtonStyle, color: 'var(--ink-2)', opacity: 0.7 }}
            >
              dismiss
            </button>
          </div>
        </div>
      ))}
      {total === 0 ? (
        <div style={{ ...homeEmptyState, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div>nothing waiting for you</div>
          <div style={{ fontSize: 10 }}>proposed actions and decisions will land here when there are any</div>
        </div>
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
                    {friendlyLabel(action.kind)} · {action.risk_tier} · {action.source_kind}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void handleApprove(action)}
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
              {action.payload && Object.keys(action.payload).length > 0 && (
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: 'var(--ink-2)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1,
                  }}
                >
                  {Object.entries(action.payload).map(([key, value]) => (
                    <div key={key}>
                      {key}: {typeof value === 'string' ? value : JSON.stringify(value)}
                    </div>
                  ))}
                </div>
              )}
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
  onNavigate,
}: {
  onNavigate: (view: string) => void;
}) {
  // This card owns the /todos query. Do not borrow Brief's state: a healthy
  // todos response must remain truthful even when another dashboard card is
  // slow or unavailable.
  const { data: todos = [], isPending, isError, error, refetch } = useTodos();

  const open = todos.filter((t) => t.status === 'pending' || t.status === 'active');

  if (isPending) {
    return (
      <SectionCard title="today">
        <div role="status" style={homeEmptyState}>
          loading…
        </div>
      </SectionCard>
    );
  }

  if (isError) {
    return (
      <SectionCard title="today">
        <ErrorCard message={describeFailure(error)} onRetry={() => refetch()} />
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
        <div style={{ ...homeEmptyState, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div>nothing on the list</div>
          <div style={{ fontSize: 10 }}>your day is wide open</div>
        </div>
      ) : (
        open.slice(0, 5).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onNavigate('tasks')}
            style={{
              ...itemCard,
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
              textAlign: 'left',
              width: '100%',
              cursor: 'pointer',
              padding: '8px 10px',
              background: 'transparent',
              border: '1px solid transparent',
              borderRadius: 6,
              transition: 'border-color 150ms ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--line)' }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'transparent' }}
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
          </button>
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
      <div style={{ ...bodyText, fontSize: 12 }}>
        quick capture — drop a file or click below to save it for later
      </div>
      <CapturePanel />
    </SectionCard>
  );
}

const homeDisclosureStyle: React.CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-separator)',
  borderRadius: 14,
  overflow: 'hidden',
};

const homeSummaryStyle: React.CSSProperties = {
  cursor: 'pointer',
  padding: '13px 15px',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 650,
  color: 'var(--color-text-secondary)',
  listStylePosition: 'inside',
};

const homeDisclosureGridStyle: React.CSSProperties = {
  display: 'grid',
  gap: 14,
  padding: '0 14px 14px',
  alignItems: 'start',
};

// ── Root ─────────────────────────────────────────────────────────────────────

interface Props {
  compact?: boolean;
  preferredName?: string;
  onDecideInChat?: (entry: GatewayTriageEntry) => void;
  onNavigate?: (view: string) => void;
  onExpertClick?: (expert: ExpertProfile) => void;
}

export function HomeState({
  compact = false,
  preferredName = '',
  onDecideInChat = () => {},
  onNavigate = () => {},
  onExpertClick,
}: Props) {
  const { visibleTiles } = useDashboardConfig();
  const weatherQuery = useGatewayWeather();
  const repairs = useRepairs();
  const weather = weatherQuery.data?.weather;
  const systemNeedsAttention = !repairs.isPending && (
    repairs.isError ||
    !repairs.data ||
    repairs.data.checks_run === 0 ||
    repairs.data.repairs.some((repair) => repair.severity !== 'ok')
  );
  const [systemOpen, setSystemOpen] = useState(false);

  useEffect(() => {
    if (systemNeedsAttention) setSystemOpen(true);
  }, [systemNeedsAttention]);

  return (
    <div
      data-testid="home-daily-overview"
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: compact ? '16px 12px 40px' : '28px 28px 48px',
        background: 'var(--color-canvas)',
      }}
    >
      <div
        data-testid="home-daily-overview-content"
        style={{
          width: '100%',
          maxWidth: 1120,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          gap: compact ? 14 : 18,
        }}
      >
        <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20 }}>
          <div style={{ minWidth: 0 }}>
            <h1
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: compact ? 24 : 32,
                lineHeight: 1.05,
                fontWeight: 800,
                letterSpacing: '-0.03em',
                color: 'var(--color-text-primary)',
                margin: 0,
              }}
            >
              {greeting(new Date().getHours())}{preferredName ? `, ${preferredName}` : ''}
            </h1>
            <p style={{ margin: '7px 0 0', fontSize: 13, color: 'var(--color-text-muted)' }}>
              what matters now, then what&apos;s waiting
            </p>
          </div>
          {visibleTiles['weather'] !== false && weather && !weather.error && !compact && (
            <div aria-label="Weather" style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
                {weather.temp_c != null ? `${Math.round(weather.temp_c)}°C` : '—'}
              </div>
              {weather.description && (
                <div style={{ marginTop: 2, fontSize: 12, color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                  {weather.description}
                </div>
              )}
            </div>
          )}
        </header>

        {visibleTiles['health'] !== false && <HealthStrip />}

        <section
          data-testid="home-primary-overview"
          aria-label="Daily priorities"
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))',
            gap: compact ? 12 : 16,
            alignItems: 'start',
          }}
        >
          {visibleTiles['whats-next'] !== false && (
            <WhatsNext preferredName={preferredName} onDecideInChat={onDecideInChat} onNavigate={onNavigate} />
          )}
          {visibleTiles['needs-you'] !== false && <NeedsYou onDecideInChat={onDecideInChat} />}
          {visibleTiles['today'] !== false && <TodayPanel onNavigate={onNavigate} />}
          {visibleTiles['deadlines'] !== false && <Deadlines />}
          {visibleTiles['active-projects'] !== false && <ActiveProjects onNavigate={onNavigate} />}
        </section>

        {visibleTiles['capture'] !== false && <CaptureSection />}

        <details data-testid="home-more-context" style={homeDisclosureStyle}>
          <summary style={homeSummaryStyle}>More context</summary>
          <div style={{ ...homeDisclosureGridStyle, gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))' }}>
            {visibleTiles['insight-loop'] !== false && <InsightReturnCard />}
            {visibleTiles['what-changed'] !== false && <WhatChanged />}
            {visibleTiles['active-projects'] !== false && <ExpertStrip onExpertClick={onExpertClick ?? (() => {})} />}
          </div>
        </details>

        <details
          data-testid="home-system-details"
          style={homeDisclosureStyle}
          open={systemOpen}
          onToggle={(event) => setSystemOpen(event.currentTarget.open)}
        >
          <summary style={homeSummaryStyle}>System &amp; setup</summary>
          <div style={{ ...homeDisclosureGridStyle, gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))' }}>
            {visibleTiles['health'] !== false && <HealthSurfaceCard />}
            {visibleTiles['health'] !== false && <RepairsCard />}
            {visibleTiles['health'] !== false && <SignalsCard />}
            <BuilderGlance onOpen={() => onNavigate('work')} />
            {visibleTiles['phone-access'] !== false && <PhoneAccessCard />}
          </div>
        </details>
      </div>
    </div>
  );
}
