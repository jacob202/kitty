import { render, screen, cleanup, fireEvent, within } from '@testing-library/react';
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import {
  useStateChanges,
  useActions,
  useApproveAction,
  useExecuteAction,
  useRejectAction,
  useTodos,
  useNeedsJacob,
  useSnapshotState,
  useStateNow,
  useRunInboxTriage,
  useProjects,
  useProjectNextSteps,
  useWhatsNextSteps,
  useGatewayHealth,
  useHealthSurface,
  useGatewayWeather,
  useIntelligence,
  useRefreshIntelligenceConnections,
  useGatewayModels,
  useChatsPersistence,
  useSessionContext,
  useDeadlines,
  useDeadlineSweep,
  useGatewayRuntimeManifest,
  useTailnet,
  useRepairs,
  useExecuteRepair,
  useExpertList,
  useSignals,
} from '../src/lib/queries';
import { HomeState } from '../src/components/HomeState';

vi.mock('../src/components/CapturePanel', () => ({
  CapturePanel: () => <div data-testid="capture-panel" />,
}));

vi.mock('../src/components/InsightReturnCard', () => ({
  InsightReturnCard: () => <div data-testid="insight-return-card" />,
}));

vi.mock('../src/components/BuilderSurface', () => ({
  BuilderGlance: ({ onOpen }: { onOpen: () => void }) => (
    <button type="button" onClick={onOpen}>Open Builder</button>
  ),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock('../src/lib/queries', () => ({
  useStateChanges: vi.fn(),
  useActions: vi.fn(),
  useApproveAction: vi.fn(),
  useExecuteAction: vi.fn(),
  useRejectAction: vi.fn(),
  useTodos: vi.fn(),
  useNeedsJacob: vi.fn(),
  useSnapshotState: vi.fn(),
  useStateNow: vi.fn(),
  useRunInboxTriage: vi.fn(),
  useProjects: vi.fn(),
  useProjectNextSteps: vi.fn(),
  useWhatsNextSteps: vi.fn(),
  useGatewayHealth: vi.fn(),
  useHealthSurface: vi.fn(),
  useGatewayWeather: vi.fn(),
  useGatewayModels: vi.fn(),
  useChatsPersistence: vi.fn(),
  useSessionContext: vi.fn(),
  useDeadlines: vi.fn(),
  useDeadlineSweep: vi.fn(),
  useGatewayRuntimeManifest: vi.fn(),
  useTailnet: vi.fn(),
  useRepairs: vi.fn(),
  useExecuteRepair: vi.fn(),
  useExpertList: vi.fn(),
  useSignals: vi.fn(),
  useIntelligence: vi.fn(),
  useRefreshIntelligenceConnections: vi.fn(),
}));

const LIVE_MODELS = [
  { id: 'kitty-sonnet', name: 'sonnet', color: '#4D9FFF', glow: '#4D9FFF99' },
  { id: 'kitty-local', name: 'local', color: '#35B7A6', glow: '#35B7A699' },
];

function setDefaultMocks() {
  (useStateChanges as Mock).mockReturnValue({
    data: { changes: [], new_signals: [], note: undefined },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useActions as Mock).mockReturnValue({
    data: [],
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useApproveAction as Mock).mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
  (useExecuteAction as Mock).mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
  (useRejectAction as Mock).mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
  (useTodos as Mock).mockReturnValue({
    data: [],
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useNeedsJacob as Mock).mockReturnValue({
    data: { entries: [] },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useSnapshotState as Mock).mockReturnValue({ isPending: false, mutate: vi.fn() });
  (useStateNow as Mock).mockReturnValue({
    data: { ts: 0, sections: { inbox: { ok: true, untriaged_count: 0 } } },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useRunInboxTriage as Mock).mockReturnValue({ isPending: false, mutate: vi.fn() });
  (useProjects as Mock).mockReturnValue({
    data: [],
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useProjectNextSteps as Mock).mockReturnValue([]);
  (useWhatsNextSteps as Mock).mockReturnValue({ data: null, isPending: false, isError: false, isFetched: true });
  (useGatewayHealth as Mock).mockReturnValue({
    data: { ok: true, litellmReachable: true, error: null },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useHealthSurface as Mock).mockReturnValue({
    data: {
      ok: true,
      generated_at: '2026-08-23T00:00:00Z',
      overall: 'healthy',
      domains: [
        { name: 'gateway', status: 'available', reason: '', detail: {} },
        { name: 'database', status: 'available', reason: '', detail: {} },
        { name: 'memory', status: 'available', reason: '', detail: {} },
        { name: 'automation_supervisor', status: 'available', reason: '', detail: {} },
        { name: 'cron', status: 'available', reason: '', detail: {} },
        { name: 'telegram', status: 'available', reason: '', detail: {} },
        { name: 'image_lab', status: 'available', reason: '', detail: {} },
        { name: 'image_providers', status: 'available', reason: '', detail: {} },
        { name: 'image_queue', status: 'available', reason: '', detail: {} },
        { name: 'ollama', status: 'available', reason: '', detail: {} },
        { name: 'pending_grants', status: 'available', reason: '', detail: { count: 0 } },
      ],
      degraded: [],
      still_functional: ['gateway', 'database', 'memory', 'automation_supervisor', 'cron', 'telegram', 'image_lab', 'image_providers', 'image_queue', 'ollama', 'pending_grants'],
      pending_grants: 0,
    },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useGatewayWeather as Mock).mockReturnValue({
    data: null,
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useIntelligence as Mock).mockReturnValue({
    data: { items: [], counts: { shown: 0, total_candidates: 0 }, sources: {} },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useRefreshIntelligenceConnections as Mock).mockReturnValue({ isPending: false, mutate: vi.fn() });
  (useGatewayModels as Mock).mockReturnValue({
    data: { models: LIVE_MODELS, fromLiveGateway: true, error: null },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useChatsPersistence as Mock).mockReturnValue({
    data: { ok: true, count: 3, error: null },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useSessionContext as Mock).mockReturnValue({
    data: { current_branch: 'main', last_session_topic: 'UI wiring fix pass', open_threads: [], next_actions: [] },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useDeadlines as Mock).mockReturnValue({
    data: { deadlines: [], fromLiveGateway: true, error: null },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useDeadlineSweep as Mock).mockReturnValue({
    isPending: false,
    mutate: vi.fn(),
    data: undefined,
  });
  (useTailnet as Mock).mockReturnValue({
    data: { ok: false, tailnetIp: null, uiUrl: null },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useGatewayRuntimeManifest as Mock).mockReturnValue({
    data: {
      execution: {
        builder: {
          state: 'available',
          value: {
            schema_version: 1,
            queue: { total: 0, queued: 0, claimed: 0, running: 0, blocked: 0, pr_opened: 0, awaiting_review: 0, done: 0, failed: 0, cancelled: 0 },
            initiatives: [],
          },
          source: 'builder_status',
          observed_at: '2026-07-17T03:00:00Z',
          valid_until: '2026-07-17T03:05:00Z',
        },
      },
    },
    isLoading: false,
    error: null,
  });
  (useRepairs as Mock).mockReturnValue({
    data: {
      ok: true,
      checks_run: 1,
      issues: 0,
      repairs: [{ id: 'test', severity: 'ok', title: 'All systems healthy', detail: '' }],
    },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useExecuteRepair as Mock).mockReturnValue({ isPending: false, mutate: vi.fn() });
  (useExpertList as Mock).mockReturnValue({
    data: [],
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useSignals as Mock).mockReturnValue({
    data: { ok: true, checks_run: 0, issues: 0, repairs: [] },
    isPending: false,
    isError: false,
    isFetched: true,
  });
}

const DEADLINE = {
  id: 5,
  project_id: 2,
  source: 'knowledge:said-letter',
  source_id: null,
  due_date: '2099-01-15',
  obligation: 'Return the SAID income form',
  amount: null,
  currency: null,
  confidence: 'high' as const,
  status: 'open' as const,
  dedupe_key: 'deadline:knowledge:abc',
  created_at: 0,
  updated_at: 0,
  pushed_at: null,
};

const PROJECT = {
  id: 1,
  name: 'benefits-admin',
  kind: 'admin',
  status: 'active',
  summary: '',
  paths: [],
  last_touched: null,
  open_questions: [],
  next_actions: [],
  links: [],
};

const STEP = {
  project_id: 1,
  step: 'Call SAID about the missing form',
  why: 'deadline is Friday',
  recent_win: '',
  delegable: false,
  generated_at: 100,
};

describe('HomeState', () => {
  beforeEach(setDefaultMocks);
  afterEach(cleanup);

  it('renders the cockpit section titles', () => {
    render(<HomeState />);
    expect(screen.getByText("what's next")).toBeInTheDocument();
    expect(screen.getByText('active projects')).toBeInTheDocument();
    expect(screen.getByText('needs you')).toBeInTheDocument();
    expect(screen.getByText('what changed')).toBeInTheDocument();
    expect(screen.getByText('today')).toBeInTheDocument();
    expect(screen.getByText('capture')).toBeInTheDocument();
  });

  it('never renders the gateway snapshot API instruction on Home', () => {
    (useStateChanges as Mock).mockReturnValue({
      data: {
        baseline_ts: null,
        current_ts: 0,
        changes: [],
        new_signals: [],
        note: 'no snapshot yet — POST /state/snapshot to create a baseline',
      },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.queryByText(/POST \/state\/snapshot/i)).not.toBeInTheDocument();
    expect(screen.getByText(/no comparison point yet/i)).toBeInTheDocument();
  });

  it('shows honest empty states when gateway returns no data', () => {
    (useSessionContext as Mock).mockReturnValue({
      data: { current_branch: 'main', last_session_topic: null, open_threads: [], next_actions: [] },
      isPending: false,
      isError: false,
    });
    render(<HomeState />);
    expect(screen.getByText(/not enough signal yet/)).toBeInTheDocument();
    expect(screen.getByText(/no projects registered — add one from the projects view/)).toBeInTheDocument();
    expect(screen.getByText('nothing new since last snapshot')).toBeInTheDocument();
    expect(screen.getByText('nothing waiting for you')).toBeInTheDocument();
    expect(screen.getByText('nothing on the list')).toBeInTheDocument();
  });

  // ── health strip ──

  it('shows all-green health strip when everything answers', () => {
    render(<HomeState />);
    expect(screen.getByText('Kitty is connected')).toBeInTheDocument();
    expect(screen.getByText('models ready · 2')).toBeInTheDocument();
    expect(screen.getByText('saved chats · 3')).toBeInTheDocument();
    expect(screen.getByText('retry')).toBeInTheDocument();
    expect(screen.getByRole('status')).not.toHaveTextContent(/gateway/i);
  });

  it('translates saved-chat transport failures before they reach the health strip', () => {
    (useChatsPersistence as Mock).mockReturnValue({
      data: { ok: false, count: 0, error: 'Gateway returned 404 Not Found' },
      isPending: false,
      isError: false,
      isFetched: true,
    });

    render(<HomeState />);

    const health = screen.getByRole('status');
    expect(health).toHaveTextContent("Kitty is running but this part isn't answering yet")
    expect(health).not.toHaveTextContent('Gateway returned 404 Not Found')
  });

  it('keeps internal Builder repair jargon out of ordinary Home copy', () => {
    (useRepairs as Mock).mockReturnValue({
      data: {
        ok: false, checks_run: 2, issues: 2,
        repairs: [
          { id: 'history', severity: 'warn', title: 'Builder has incomplete transition history', detail: '14 task(s) changed state without transition history' },
          { id: 'packets', severity: 'warn', title: 'Builder status includes 2 partial packet records', detail: '2 partial packet records found' },
        ],
      },
      isPending: false, isError: false, isFetched: true,
    });

    render(<HomeState />);
    expect(screen.queryByText(/transition history/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/packet records/i)).not.toBeInTheDocument()
    expect(screen.getByText('Builder activity history needs attention')).toBeVisible()
    expect(screen.getByText('Some Builder work is incomplete')).toBeVisible()
  });

  it('surfaces material health failures without making the user hunt for them', () => {
    (useRepairs as Mock).mockReturnValue({
      data: {
        ok: false,
        checks_run: 4,
        issues: 4,
        repairs: [
          { id: 'core', severity: 'error', title: "Kitty's core service is unavailable", detail: '' },
          { id: 'memory', severity: 'error', title: 'Memory search is temporarily unavailable', detail: '' },
          { id: 'background', severity: 'warn', title: 'A background service needs setup', detail: '' },
          { id: 'search', severity: 'warn', title: 'Search indexing needs attention', detail: '' },
        ],
      },
      isPending: false,
      isError: false,
      isFetched: true,
    });

    render(<HomeState />);

    expect(screen.getByTestId('home-system-details')).toHaveAttribute('open');
    expect(screen.getByText('Kitty needs attention · 4 issues')).toBeVisible();
    expect(screen.getByText("Kitty's core service is unavailable")).toBeVisible();
  });

  it('shows the gateway down fix when the gateway is down', () => {
    (useGatewayHealth as Mock).mockReturnValue({
      data: { ok: false, litellmReachable: false, error: 'Could not reach the gateway' },
      isPending: false,
    });
    render(<HomeState />);
    expect(
      screen.getAllByText(/Kitty is not connected — check if Kitty is running/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText('models unknown')).toBeInTheDocument();
    expect(screen.getByRole('status')).not.toHaveTextContent(/gateway/i);
  });

  it('uses product language while the health strip is still checking', () => {
    (useGatewayHealth as Mock).mockReturnValue({ data: undefined, isPending: true });
    (useGatewayModels as Mock).mockReturnValue({ data: undefined, isPending: true });
    (useChatsPersistence as Mock).mockReturnValue({ data: undefined, isPending: true });
    render(<HomeState />);
    expect(screen.getByText('checking Kitty connection — status lands here in a sec…')).toBeInTheDocument();
    expect(screen.getByRole('status')).not.toHaveTextContent(/gateway/i);
  });

  it('does not call fallback models ready when the live model read failed', () => {
    (useGatewayModels as Mock).mockReturnValue({
      data: { models: LIVE_MODELS, fromLiveGateway: false, error: 'Could not read /api/models' },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getByText('model list unavailable')).toBeInTheDocument();
    expect(screen.queryByText(/models ready/)).not.toBeInTheDocument();
  });

  it('shows model routing unavailable from the /health probe, never a fake routing-live', () => {
    (useGatewayHealth as Mock).mockReturnValue({
      data: { ok: true, litellmReachable: false, error: null },
      isPending: false,
    });
    render(<HomeState />);
    expect(screen.getByText(/models are unavailable/)).toBeInTheDocument();
    expect(screen.queryByText(/models ready/)).not.toBeInTheDocument();
  });

  // ── health surface (full-stack projection) ──

  it('renders every domain row and the still-functional section when healthy', () => {
    render(<HomeState />);
    expect(screen.getByText('health')).toBeInTheDocument();
    // each healthy domain appears in the rows grid and again in the
    // "still functional" section — duplicate presence is intended
    expect(screen.getAllByText('Kitty connection').length).toBeGreaterThan(0);
    expect(screen.getAllByText('saved data').length).toBeGreaterThan(0);
    expect(screen.getAllByText('background tasks').length).toBeGreaterThan(0);
    expect(screen.getAllByText('image lab').length).toBeGreaterThan(0);
    expect(screen.getAllByText('image creation').length).toBeGreaterThan(0);
    expect(screen.getAllByText('image jobs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('pending approvals').length).toBeGreaterThan(0);
    expect(document.body.textContent ?? '').not.toMatch(/\bcron\b|\btelegram\b|\bollama\b|image providers|image queue/i);
    expect(screen.getByText('still functional')).toBeInTheDocument();
    expect(screen.queryByText('degraded')).not.toBeInTheDocument();
  });

  it('lists degraded domains and expands the reason on click', async () => {
    (useHealthSurface as Mock).mockReturnValue({
      data: {
        ok: true,
        generated_at: '2026-08-23T00:00:00Z',
        overall: 'degraded',
        domains: [
          { name: 'gateway', status: 'available', reason: '', detail: {} },
          { name: 'image_lab', status: 'available', reason: '', detail: {} },
          {
            name: 'ollama',
            status: 'unavailable',
            // The exact string gateway/health_surface.py builds for this domain.
            reason:
              'embedding runtime unreachable at http://localhost:11434: ConnectionError; explicit memory remains available independently',
            detail: {},
          },
          { name: 'pending_grants', status: 'available', reason: '', detail: { count: 0 } },
        ],
        degraded: ['ollama'],
        still_functional: ['gateway', 'image_lab'],
        pending_grants: 0,
      },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    // card-header count and section heading both read "degraded"
    expect(screen.getAllByText('degraded').length).toBeGreaterThan(0);
    expect(screen.getByText('still functional')).toBeInTheDocument();
    // reason is hidden until the row is expanded
    expect(screen.queryByText(/embedding runtime/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /local AI/i }));
    expect(await screen.findByText('collapse')).toBeInTheDocument();
    // the cause is translated, and it says what still works
    expect(
      screen.getByText(/The local AI behind search and memory isn't answering/i),
    ).toBeInTheDocument();
    // the raw reason stays reachable for debugging, but only behind the disclosure
    const details = screen.getByText('Technical details').closest('details');
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute('open');
    expect(details?.textContent).toContain('ConnectionError');
  });

  it('falls back to status copy when the reason is not a cause it recognises', async () => {
    (useHealthSurface as Mock).mockReturnValue({
      data: {
        ok: true,
        generated_at: '2026-08-23T00:00:00Z',
        overall: 'degraded',
        domains: [
          { name: 'gateway', status: 'available', reason: '', detail: {} },
          { name: 'ollama', status: 'unavailable', reason: 'OLLAMA_BASE is not reachable', detail: {} },
        ],
        degraded: ['ollama'],
        still_functional: ['gateway'],
        pending_grants: 0,
      },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    fireEvent.click(screen.getByRole('button', { name: /local AI/i }));
    expect(await screen.findByText('collapse')).toBeInTheDocument();
    // an unrecognised reason must not become the sentence the user reads
    expect(screen.getByText(/This part of Kitty is unavailable right now/i)).toBeInTheDocument();
    const summary = screen.getByText('Technical details');
    expect(summary.closest('details')).not.toHaveAttribute('open');
  });

  it('surfaces the pending approvals count when grants await', () => {
    (useHealthSurface as Mock).mockReturnValue({
      data: {
        ok: true,
        generated_at: '2026-08-23T00:00:00Z',
        overall: 'healthy',
        domains: [
          { name: 'gateway', status: 'available', reason: '', detail: {} },
          { name: 'pending_grants', status: 'available', reason: '', detail: { count: 2 } },
        ],
        degraded: [],
        still_functional: ['gateway', 'pending_grants'],
        pending_grants: 2,
      },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getByText('2 pending approvals waiting on you')).toBeInTheDocument();
  });

  it('shows a plain-language failure message and a working retry when the health surface fails to load', () => {
    const refetch = vi.fn();
    (useHealthSurface as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
      refetch,
    });
    render(<HomeState />);
    const heading = screen.getByText('health');
    const sectionCard = heading.parentElement!.parentElement as HTMLElement;
    expect(within(sectionCard).getByText("Kitty is running but this part isn't answering yet.")).toBeInTheDocument();
    expect(within(sectionCard).queryByText('health surface unavailable')).not.toBeInTheDocument();
    expect(within(sectionCard).queryByText(/Gateway returned/)).not.toBeInTheDocument();
    within(sectionCard).getByRole('button', { name: 'retry loading' }).click();
    expect(refetch).toHaveBeenCalled();
  });

  // ── what's next hero ──

  it('puts a proposed action first in the hero, with working verbs', () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined);
    (useApproveAction as Mock).mockReturnValue({ isPending: false, mutateAsync });
    (useActions as Mock).mockReturnValue({
      data: [
        {
          id: 7,
          title: 'Send the SAID follow-up email',
          preview: '',
          kind: 'email',
          risk_tier: 'T1',
          source_kind: 'agent',
        },
      ],
      isPending: false,
      isError: false,
    });
    // project step also present — action must win
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useWhatsNextSteps as Mock).mockReturnValue({ data: [STEP], isPending: false, isError: false, isFetched: true });
    render(<HomeState />);
    expect(screen.getAllByText('Send the SAID follow-up email').length).toBeGreaterThan(0);
    expect(screen.getByText(/waiting on your approval/)).toBeInTheDocument();
  });

  it('falls back to the life-first project next-step when nothing is proposed', () => {
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useWhatsNextSteps as Mock).mockReturnValue({ data: [STEP], isPending: false, isError: false, isFetched: true });
    const onNavigate = vi.fn();
    render(<HomeState onNavigate={onNavigate} />);
    expect(screen.getAllByText('Call SAID about the missing form').length).toBeGreaterThan(0);
    expect(screen.getByText(/why: deadline is Friday/)).toBeInTheDocument();
    screen.getByText('open projects').click();
    expect(onNavigate).toHaveBeenCalledWith('projects');
  });

  it('falls back to the top todo when there are no actions or steps', () => {
    (useTodos as Mock).mockReturnValue({
      data: [{ id: 1, content: 'book dentist', status: 'pending' }],
      isPending: false,
    });
    render(<HomeState />);
    expect(screen.getAllByText('book dentist').length).toBeGreaterThan(0);
    expect(screen.getByText(/nothing louder is waiting/)).toBeInTheDocument();
  });

  it('shows the last session topic when nothing more urgent is waiting', () => {
    render(<HomeState />);
    expect(screen.getByText('last session: UI wiring fix pass')).toBeInTheDocument();
  });

  it('shows a plain-language failure message in the hero when actions fail, without repeating the gateway-offline banner', () => {
    (useActions as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
      refetch: vi.fn(),
    });
    render(<HomeState />);
    expect(screen.getAllByText("Kitty is running but this part isn't answering yet.").length).toBeGreaterThan(0);
    expect(screen.queryByText('unavailable')).not.toBeInTheDocument();
    expect(screen.queryByText(/404/)).not.toBeInTheDocument();
  });

  it("shows a plain-language error with a retry button when /session/context fails, not a loading spinner", () => {
    (useSessionContext as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
    });
    render(<HomeState />);
    // Must show an error alert with plain-language copy, not a loading spinner
    // and never the raw HTTP diagnostic text.
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toMatch(/Kitty is running but this part isn't answering yet\./);
    expect(alert.textContent).not.toMatch(/404/);
    expect(alert.textContent).not.toMatch(/Gateway returned/);
    expect(screen.queryByText('loading…')).not.toBeInTheDocument();
    // Must include a retry control (HealthStrip also has one, so at least 1)
    expect(screen.getAllByRole('button', { name: 'retry' }).length).toBeGreaterThanOrEqual(1);
    // The error card's retry lives inside the alert
    expect(screen.getByRole('alert').querySelector('button')).toBeTruthy();
  });

  it("retry in whats-next recovers when the query succeeds on re-render", () => {
    (useSessionContext as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('504'),
    });
    const { rerender } = render(<HomeState />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    // Simulate recovery after retry
    (useSessionContext as Mock).mockReturnValue({
      data: { current_branch: 'main', last_session_topic: null, open_threads: [], next_actions: [] },
      isPending: false,
      isError: false,
    });
    rerender(<HomeState />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText(/not enough signal yet/)).toBeInTheDocument();
  });

  // ── active projects ──

  it('lists active projects with their next step', () => {
    (useProjects as Mock).mockReturnValue({
      data: [PROJECT, { ...PROJECT, id: 2, name: 'kitty', kind: 'code', status: 'parked' }],
      isPending: false,
      isError: false,
    });
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: STEP, isPending: false, isError: false },
      { data: null, isPending: false, isError: false },
    ]);
    render(<HomeState />);
    expect(screen.getByText('benefits-admin')).toBeInTheDocument();
    // parked project stays out of the active list
    expect(screen.queryByText('kitty')).not.toBeInTheDocument();
  });

  it('keeps project setup internals out of Home next-step copy', () => {
    const rawStep = {
      ...STEP,
      project_id: 1,
      step: 'Register the benefits-admin project paths in your tracker, then refresh the project state once.',
      why: 'There is no usable project data yet, so make the tracker able to see the repo.',
      recent_win: '',
    };
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useWhatsNextSteps as Mock).mockReturnValue({ data: [rawStep], isPending: false, isError: false });
    (useProjectNextSteps as Mock).mockReturnValue([{ data: rawStep, isPending: false, isError: false }]);
    (useActions as Mock).mockReturnValue({ data: [], isPending: false, isError: false });
    (useNeedsJacob as Mock).mockReturnValue({ data: { entries: [] }, isPending: false, isError: false });
    (useTodos as Mock).mockReturnValue({ data: [], isPending: false, isError: false });

    render(<HomeState />);

    const copy = document.body.textContent ?? '';
    expect(copy).not.toMatch(/project paths|tracker|\brepo\b/i);
    expect(screen.getAllByText('Kitty needs more project context before it can suggest a next step.').length).toBeGreaterThan(0);
  });

  it('describes phone access without exposing its infrastructure dependency', () => {
    render(<HomeState />);
    expect(document.body.textContent ?? '').not.toMatch(/Tailscale/i);
    expect(screen.getByText(/Phone access needs its secure connection app running on this Mac/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /open phone access/i })).toBeInTheDocument();
  });

  it('shows a plain-language failure message and a working retry when active projects fails to load', () => {
    const refetch = vi.fn();
    (useProjects as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
      refetch,
    });
    render(<HomeState />);
    const heading = screen.getByText('active projects');
    const sectionCard = heading.parentElement!.parentElement as HTMLElement;
    expect(within(sectionCard).getByText("Kitty is running but this part isn't answering yet.")).toBeInTheDocument();
    expect(within(sectionCard).queryByText('unavailable')).not.toBeInTheDocument();
    expect(within(sectionCard).queryByText(/Gateway returned/)).not.toBeInTheDocument();
    within(sectionCard).getByRole('button', { name: 'retry loading' }).click();
    expect(refetch).toHaveBeenCalled();
  });

  it('says so when a project has no generated step yet', () => {
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: null, isPending: false, isError: false },
    ]);
    (useActions as Mock).mockReturnValue({ data: [], isPending: false, isError: false });
    render(<HomeState />);
    expect(screen.getByText(/no next step yet — refresh it in projects/)).toBeInTheDocument();
  });

  // ── carried-over cards ──

  it('shows loading indicators when queries are pending', () => {
    (useStateChanges as Mock).mockReturnValue({ data: undefined, isPending: true, isError: false });
    (useActions as Mock).mockReturnValue({ data: undefined, isPending: true, isError: false });
    (useTodos as Mock).mockReturnValue({ data: undefined, isPending: true, isError: false });
    render(<HomeState />);
    const statuses = screen.getAllByRole('status');
    expect(statuses.length).toBeGreaterThan(0);
  });

  it('shows a plain-language failure message when the actions query fails, without repeating the gateway-offline banner', () => {
    (useActions as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
      refetch: vi.fn(),
    });
    render(<HomeState />);
    // Both "what's next" and "needs you" read useActions, so both show the
    // plain-language failure message.
    expect(screen.getAllByText("Kitty is running but this part isn't answering yet.").length).toBeGreaterThan(0);
    expect(screen.queryByText('unavailable')).not.toBeInTheDocument();
  });

  it('retries the actions query when "needs you" retry is clicked', () => {
    const refetch = vi.fn();
    (useActions as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
      refetch,
    });
    render(<HomeState />);
    const heading = screen.getByText('needs you');
    const sectionCard = heading.parentElement!.parentElement as HTMLElement;
    within(sectionCard).getByRole('button', { name: 'retry loading' }).click();
    expect(refetch).toHaveBeenCalled();
  });

  it('shows an unavailable card when the state changes query fails, without repeating the gateway-offline banner', () => {
    (useStateChanges as Mock).mockReturnValue({ data: undefined, isPending: false, isError: true });
    render(<HomeState />);
    expect(screen.getByText('unavailable')).toBeInTheDocument();
  });

  it('fetches unresolved action statuses directly so old failures cannot be crowded out by terminal history', () => {
    const failedAction = {
      id: 77, title: 'Old failed action', preview: 'needs review', kind: 'note.draft',
      risk_tier: 'T1', source_kind: 'agent', status: 'failed', created_at: '',
      source_id: null, payload: {}, result: 'provider failed', decided_at: null, executed_at: null,
    };
    (useActions as Mock).mockImplementation((status?: string) => ({
      data: status === 'failed' ? [failedAction] : [],
      isPending: false, isError: false, isFetched: true, refetch: vi.fn(),
    }));

    render(<HomeState />);

    expect(useActions).toHaveBeenCalledWith('approved');
    expect(useActions).toHaveBeenCalledWith('failed');
    expect(useActions).toHaveBeenCalledWith('unknown');
    expect(useActions).toHaveBeenCalledWith('outcome_unknown');
    expect(screen.getByText('Old failed action')).toBeVisible();
    expect(screen.getByText('provider failed')).toBeVisible();
  });

  it('shows proposed actions with approve and reject buttons in needs you', () => {
    const action = {
      id: 1,
      title: 'Deploy to prod',
      preview: 'runs deploy.sh',
      kind: 'shell',
      risk_tier: 2,
      source_kind: 'agent',
      status: 'proposed',
      created_at: '',
      source_id: null,
      payload: {},
      result: null,
      decided_at: null,
      executed_at: null,
    };
    (useActions as Mock).mockReturnValue({
      data: [action],
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getAllByText('Deploy to prod').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /approve Deploy to prod/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject Deploy to prod/i })).toBeInTheDocument();
  });

  it('fetches each unresolved action status separately so older repairs survive history limits', () => {
    const failedAction = { id: 88, title: 'Old failed action', preview: 'Needs repair', kind: 'note.draft', risk_tier: 'T1', source_kind: 'agent', status: 'failed', created_at: '', source_id: null, payload: {}, result: 'old durable failure', decided_at: null, executed_at: null }
    ;(useActions as Mock).mockImplementation((status?: string) => ({
      data: status === 'failed' ? [failedAction] : [],
      isPending: false, isError: false, isFetched: true, refetch: vi.fn(),
    }))

    render(<HomeState />)

    const requested = (useActions as Mock).mock.calls.map(([status]) => status)
    expect(requested).toEqual(expect.arrayContaining(['proposed', 'approved', 'failed', 'unknown', 'outcome_unknown']))
    expect(screen.getByText('Old failed action')).toBeInTheDocument()
    expect(screen.getByText('old durable failure')).toBeInTheDocument()
  })

  it('keeps stranded approved and failed actions visible with truthful recovery controls', () => {
    (useActions as Mock).mockReturnValue({
      data: [
        { id: 7, title: 'Approved calendar event', preview: 'Ready to run', kind: 'calendar.event.create', risk_tier: 'T2', source_kind: 'agent', status: 'approved', created_at: '', source_id: null, payload: {}, result: null, decided_at: null, executed_at: null },
        { id: 8, title: 'Failed note', preview: 'Could not save', kind: 'note.draft', risk_tier: 'T1', source_kind: 'agent', status: 'failed', created_at: '', source_id: null, payload: {}, result: 'disk unavailable', decided_at: null, executed_at: null },
      ],
      isPending: false, isError: false, isFetched: true,
    })
    render(<HomeState />)
    expect(screen.getByRole('button', { name: /run Approved calendar event/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /approve Approved calendar event/i })).not.toBeInTheDocument()
    expect(screen.getByText('disk unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /approve Failed note/i })).not.toBeInTheDocument()
  })

  it('shows the material payload arguments before approval (C7-F07)', () => {
    (useActions as Mock).mockReturnValue({
      data: [
        {
          id: 1,
          title: 'Create calendar event',
          preview: 'will create: Dentist',
          kind: 'calendar.event.create',
          risk_tier: 'T2',
          source_kind: 'agent',
          status: 'proposed',
          created_at: '',
          source_id: null,
          payload: { title: 'Dentist', start_time: '2026-08-25T14:00:00' },
          result: null,
          decided_at: null,
          executed_at: null,
        },
      ],
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getByText('title: Dentist')).toBeInTheDocument();
    expect(screen.getByText('start_time: 2026-08-25T14:00:00')).toBeInTheDocument();
  });

  it('approving an action in needs you also executes it and shows the outcome (C7-F08)', async () => {
    const action = {
      id: 1,
      title: 'Deploy to prod',
      preview: 'runs deploy.sh',
      kind: 'shell',
      risk_tier: 'T2',
      source_kind: 'agent',
      status: 'proposed',
      created_at: '',
      source_id: null,
      payload: {},
      result: null,
      decided_at: null,
      executed_at: null,
    };
    const approveMutateAsync = vi.fn().mockResolvedValue({ ...action, status: 'approved' });
    const executeMutateAsync = vi.fn().mockResolvedValue({
      ...action,
      status: 'executed',
      result: 'deployed to prod',
    });
    (useApproveAction as Mock).mockReturnValue({ isPending: false, mutateAsync: approveMutateAsync });
    (useExecuteAction as Mock).mockReturnValue({ isPending: false, mutateAsync: executeMutateAsync });
    (useActions as Mock).mockReturnValue({
      data: [action],
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);

    fireEvent.click(screen.getByRole('button', { name: /approve Deploy to prod/i }));

    expect(approveMutateAsync).toHaveBeenCalledWith(1);
    await screen.findByText(/done · Deploy to prod/);
    expect(executeMutateAsync).toHaveBeenCalledWith(1);
    expect(screen.getByText('deployed to prod')).toBeInTheDocument();
  });

  it('shows a did-not-complete outcome when execute fails after a successful approval', async () => {
    const action = {
      id: 1,
      title: 'Create calendar event',
      preview: 'will create: Dentist',
      kind: 'calendar.event.create',
      risk_tier: 'T2',
      source_kind: 'agent',
      status: 'proposed',
      created_at: '',
      source_id: null,
      payload: {},
      result: null,
      decided_at: null,
      executed_at: null,
    };
    (useApproveAction as Mock).mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ ...action, status: 'approved' }),
    });
    (useExecuteAction as Mock).mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockRejectedValue(new Error('osascript unavailable')),
    });
    (useActions as Mock).mockReturnValue({
      data: [action],
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);

    fireEvent.click(screen.getByRole('button', { name: /approve Create calendar event/i }));

    await screen.findByText(/did not complete · Create calendar event/);
    expect(screen.getByText('osascript unavailable')).toBeInTheDocument();
  });

  it('shows what changed when state diff is available', () => {
    (useStateChanges as Mock).mockReturnValue({
      data: {
        changes: [{ section: 'mood', field: 'energy', before: 'low', after: 'high' }],
        new_signals: [],
        note: undefined,
      },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getByText(/mood · energy/)).toBeInTheDocument();
    expect(screen.getByText(/low → high/)).toBeInTheDocument();
  });

  it('shows today todos filtered to pending/active status', () => {
    (useTodos as Mock).mockReturnValue({
      data: [
        { id: 1, content: 'write tests', status: 'pending' },
        { id: 2, content: 'done already', status: 'completed' },
        { id: 3, content: 'in flight', status: 'active' },
      ],
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getAllByText('write tests').length).toBeGreaterThan(0);
    expect(screen.getByText('in flight')).toBeInTheDocument();
    expect(screen.queryByText('done already')).not.toBeInTheDocument();
  });

  it('mascot doodle is aria-hidden and non-interactive so it cannot block the sweep button', () => {
    // Show the WhatsNext empty state (no signal) and the deadlines card together.
    (useSessionContext as Mock).mockReturnValue({
      data: { current_branch: 'main', last_session_topic: null, open_threads: [], next_actions: [] },
      isPending: false,
      isError: false,
    });
    render(<HomeState />);
    // Sweep button must be present and enabled
    expect(screen.getByText('sweep')).toBeInTheDocument();
    // No SVG or span inside an aria-hidden region should be a focusable element
    const hiddenEls = document.querySelectorAll('[aria-hidden] button, [aria-hidden] a, [aria-hidden] input');
    expect(hiddenEls.length).toBe(0);
  });

  it('applies compact padding when compact prop is true', () => {
    const { container } = render(<HomeState compact />);
    const grid = container.firstChild as HTMLElement;
    expect(grid.style.padding).toBe('16px 12px 40px');
  });

  it('shows needs_jacob entries as actionable cards, not a bare count', () => {
    const entry = {
      inbox_id: 'abc-123',
      ts: 0,
      bucket: 'needs_jacob',
      confidence: 0.4,
      rationale: 'Ambiguous — could be spam or a real bill.',
      model: 'kitty-smart',
      text: 'Invoice #881 attached — please review.',
      created_at: null,
    };
    (useNeedsJacob as Mock).mockReturnValue({
      data: { entries: [entry] },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    const onDecideInChat = vi.fn();
    render(<HomeState onDecideInChat={onDecideInChat} />);
    expect(screen.getAllByText(/Invoice #881/).length).toBeGreaterThan(0);
    screen.getAllByText('decide in chat')[0].click();
    expect(onDecideInChat).toHaveBeenCalledWith(entry);
  });

  it('offers a snapshot verb on What changed regardless of state', () => {
    const mutate = vi.fn();
    (useSnapshotState as Mock).mockReturnValue({ isPending: false, mutate });
    render(<HomeState />);
    screen.getByText('mark point').click();
    expect(mutate).toHaveBeenCalled();
  });

  it('shows an untriaged count with a triage-now verb inside What changed', () => {
    (useStateNow as Mock).mockReturnValue({
      data: { ts: 0, sections: { inbox: { ok: true, untriaged_count: 3 } } },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    const mutate = vi.fn();
    (useRunInboxTriage as Mock).mockReturnValue({ isPending: false, mutate });
    render(<HomeState />);
    expect(screen.getByText('3 untriaged in inbox')).toBeInTheDocument();
    screen.getByText('triage now').click();
    expect(mutate).toHaveBeenCalled();
  });

  it("shows an honest, plain-language error on Today when the gateway is down, not a misleading empty state", () => {
    const refetch = vi.fn();
    (useTodos as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
      refetch,
    });
    render(<HomeState />);
    expect(screen.getAllByText("Kitty is running but this part isn't answering yet.").length).toBeGreaterThan(0);
    expect(screen.queryByText('nothing on the list')).not.toBeInTheDocument();
    // Never the raw HTTP diagnostic text
    expect(screen.queryByText(/Gateway returned/)).not.toBeInTheDocument();
    expect(screen.queryByText(/404/)).not.toBeInTheDocument();
    // The Today panel's own retry control actually refetches the todos query.
    const heading = screen.getByText('today');
    const sectionCard = heading.parentElement!.parentElement as HTMLElement;
    within(sectionCard).getByRole('button', { name: 'retry loading' }).click();
    expect(refetch).toHaveBeenCalled();
  });

  // ── click-throughs (cards change the active view) ──

  it('routes Active projects "open" to the projects view', () => {
    // No generated step keeps the hero on its empty state, so the only
    // "open projects" control is the Active projects header button.
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: null, isPending: false, isError: false },
    ]);
    const onNavigate = vi.fn();
    render(<HomeState onNavigate={onNavigate} />);
    screen.getByRole('button', { name: /open projects/i }).click();
    expect(onNavigate).toHaveBeenCalledWith('projects');
  });

  it('routes a project row click to the projects view', () => {
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: STEP, isPending: false, isError: false },
    ]);
    const onNavigate = vi.fn();
    render(<HomeState onNavigate={onNavigate} />);
    screen.getByRole('button', { name: /open benefits-admin in projects/i }).click();
    expect(onNavigate).toHaveBeenCalledWith('projects');
  });

  it('routes Today "open" to the tasks view', () => {
    // A project step keeps the hero on "open projects", so the only "open tasks"
    // control is the Today header button.
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useWhatsNextSteps as Mock).mockReturnValue({ data: [STEP], isPending: false, isError: false, isFetched: true });
    (useTodos as Mock).mockReturnValue({
      data: [{ id: 1, content: 'write tests', status: 'pending' }],
      isPending: false,
    });
    const onNavigate = vi.fn();
    render(<HomeState onNavigate={onNavigate} />);
    screen.getByRole('button', { name: /open tasks/i }).click();
    expect(onNavigate).toHaveBeenCalledWith('tasks');
  });

  // ── next-step hero CTA routing by source ──

  it('routes the todo hero CTA to the tasks view', () => {
    (useTodos as Mock).mockReturnValue({
      data: [{ id: 1, content: 'book dentist', status: 'pending' }],
      isPending: false,
    });
    const onNavigate = vi.fn();
    render(<HomeState onNavigate={onNavigate} />);
    screen.getByText('open tasks').click();
    expect(onNavigate).toHaveBeenCalledWith('tasks');
  });

  it('routes the needs-decision hero CTA to chat with the entry as context', () => {
    const entry = {
      inbox_id: 'z-9',
      ts: 0,
      bucket: 'needs_jacob',
      confidence: 0.8,
      rationale: 'Ambiguous.',
      text: 'Is this bill real?',
      created_at: null,
    };
    (useNeedsJacob as Mock).mockReturnValue({
      data: { entries: [entry] },
      isPending: false,
      isError: false,
    });
    const onDecideInChat = vi.fn();
    render(<HomeState onDecideInChat={onDecideInChat} />);
    // Hero CTA is the first "decide in chat" (the needs-you card renders another).
    screen.getAllByText('decide in chat')[0].click();
    expect(onDecideInChat).toHaveBeenCalledWith(entry);
  });

  // ── deadlines card ──

  it('shows an honest empty state when no deadlines are tracked', () => {
    render(<HomeState />);
    expect(screen.getByText(/no deadlines tracked yet/)).toBeInTheDocument();
  });

  it('surfaces the nearest deadline when the store has open items', () => {
    (useDeadlines as Mock).mockReturnValue({
      data: {
        deadlines: [
          DEADLINE,
          { ...DEADLINE, id: 6, obligation: 'Pay the water bill', due_date: '2099-03-01' },
        ],
        fromLiveGateway: true,
        error: null,
      },
      isPending: false,
      isError: false,
    });
    render(<HomeState />);
    expect(screen.getByText('Return the SAID income form')).toBeInTheDocument();
    expect(screen.getByText('Pay the water bill')).toBeInTheDocument();
    expect(screen.queryByText(/no deadlines tracked yet/)).not.toBeInTheDocument();
  });

  it('shows an honest, plain-language offline state for deadlines when the gateway is down', () => {
    const refetch = vi.fn();
    (useDeadlines as Mock).mockReturnValue({
      data: { deadlines: [], fromLiveGateway: false, error: 'Gateway returned 404 Not Found' },
      isPending: false,
      isError: false,
      refetch,
    });
    render(<HomeState />);
    expect(screen.getByText("Kitty is running but this part isn't answering yet.")).toBeInTheDocument();
    expect(screen.queryByText('unavailable')).not.toBeInTheDocument();
    expect(screen.queryByText(/Gateway returned/)).not.toBeInTheDocument();
    // A working retry control accompanies the failure
    const alert = screen.getByRole('alert');
    within(alert).getByRole('button', { name: 'retry loading' }).click();
    expect(refetch).toHaveBeenCalled();
  });

  it('runs a sweep from the deadlines card', () => {
    const mutate = vi.fn();
    (useDeadlineSweep as Mock).mockReturnValue({ isPending: false, mutate, data: undefined });
    render(<HomeState />);
    screen.getByText('sweep').click();
    expect(mutate).toHaveBeenCalled();
  });

  it('shows how many deadline warnings the sweep actually delivered', () => {
    (useDeadlineSweep as Mock).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
      data: {
        found: 1, open: 1, needs_jacob: 0, top: null, blind_spots: [], generated_at: 'now',
        escalated: 1, escalation_failed: 0, delivery_status: 'delivered',
        delivery_message: '1 deadline warning delivered.',
      },
    });
    render(<HomeState />);
    expect(screen.getByText('1 deadline warning delivered.')).toBeInTheDocument();
  });

  it('says plainly when a due warning could not reach any phone channel', () => {
    (useDeadlineSweep as Mock).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
      data: {
        found: 1, open: 1, needs_jacob: 0, top: null, blind_spots: [], generated_at: 'now',
        escalated: 0, escalation_failed: 1, delivery_status: 'source_unavailable',
        delivery_message: 'A deadline warning was due, but nothing was delivered. Check notification setup and try again.',
      },
    });
    render(<HomeState />);
    expect(screen.getByText(/nothing was delivered/i)).toBeInTheDocument();
  });

  // ── error-before-loading regressions ──

  it("shows session context error even when another query is still loading (was: 'loading…' forever)", () => {
    (useActions as Mock).mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    });
    (useSessionContext as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Gateway returned 404 Not Found'),
    });
    render(<HomeState />);
    // The What's Next card must render an alert (its error card) rather than
    // its own loading state (the text "loading…" may still appear in other
    // sections whose queries are pending — that's unrelated).
    const alerts = screen.getAllByRole('alert');
    // At least one alert carries the plain-language /session/context failure —
    // never the raw "404" / "Gateway returned" diagnostic text.
    const sessionAlert = alerts.find((a) => a.textContent?.includes("Kitty is running but this part isn't answering yet."));
    expect(sessionAlert).toBeTruthy();
    expect(sessionAlert!.textContent).not.toMatch(/404/);
    expect(sessionAlert!.textContent).not.toMatch(/Gateway returned/);
    // The error card has a retry button inside the alert
    expect(sessionAlert!.querySelector('button')).toBeTruthy();
    // The What's Next section heading should be visible (proving the section
    // rendered content, not a fallthrough loading … that would hide the heading)
    expect(screen.getByText("what's next")).toBeInTheDocument();
  });

  it('keeps due-insight lifecycle controls mounted', () => {
    render(<HomeState />);
    expect(screen.getByTestId('insight-return-card')).toBeInTheDocument();
  });

  it('opens Work from the Builder glance', () => {
    const onNavigate = vi.fn();
    render(<HomeState onNavigate={onNavigate} />);
    screen.getByRole('button', { name: /open builder/i }).click();
    expect(onNavigate).toHaveBeenCalledWith('work');
    expect(onNavigate).not.toHaveBeenCalledWith('builder');
  });

  it('does not claim health when zero checks ran', () => {
    (useRepairs as Mock).mockReturnValue({
      data: { ok: true, checks_run: 0, issues: 0, repairs: [] },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    const systemCard = screen.getByText(/nothing was checked/).closest('div');
    expect(systemCard).toHaveTextContent('nothing was checked — Kitty could not complete its health checks');
    expect(systemCard).not.toHaveTextContent(/gateway/i);
    expect(screen.queryByText(/everything looks healthy/)).not.toBeInTheDocument();
  });

  it('claims health only when checks actually ran', () => {
    (useRepairs as Mock).mockReturnValue({
      data: { ok: true, checks_run: 4, issues: 0, repairs: [] },
      isPending: false,
      isError: false,
      isFetched: true,
    });
    render(<HomeState />);
    expect(screen.getByText(/everything looks healthy/)).toBeInTheDocument();
  });

  it('prioritizes daily work and collapses lower-signal context', () => {
    render(<HomeState />);

    const overview = screen.getByTestId('home-primary-overview');
    expect(overview).toHaveTextContent("what's next");
    expect(overview).toHaveTextContent('needs you');
    expect(overview).toHaveTextContent('today');
    expect(overview).toHaveTextContent('deadlines');
    expect(overview).toHaveTextContent('active projects');

    const more = screen.getByTestId('home-more-context');
    const system = screen.getByTestId('home-system-details');
    expect(more).not.toHaveAttribute('open');
    expect(system).not.toHaveAttribute('open');
    expect(more).toHaveTextContent('what changed');
    expect(system).toHaveTextContent('health');
    expect(system).toHaveTextContent(/builder/i);

    expect(overview.compareDocumentPosition(more) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(more.compareDocumentPosition(system) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('uses the same bounded daily-overview composition on phone', () => {
    render(<HomeState compact />);
    const root = screen.getByTestId('home-daily-overview');
    expect(root).toBeInTheDocument();
    const content = screen.getByTestId('home-daily-overview-content');
    expect(content.getAttribute('style') ?? '').toContain('max-width: 1120px');
    const primary = screen.getByTestId('home-primary-overview');
    expect(primary.getAttribute('style') ?? '').toContain('grid-template-columns: 1fr');
  });

});
