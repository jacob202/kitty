import { render, screen, cleanup } from '@testing-library/react';
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import {
  useStateChanges,
  useActions,
  useApproveAction,
  useRejectAction,
  useTodos,
  useNeedsJacob,
  useSnapshotState,
  useStateNow,
  useRunInboxTriage,
  useProjects,
  useProjectNextSteps,
  useGatewayHealth,
  useGatewayModels,
  useChatsPersistence,
  useSessionContext,
  useDeadlines,
  useDeadlineSweep,
} from '../src/lib/queries';
import { HomeState } from '../src/components/HomeState';

vi.mock('../src/components/CapturePanel', () => ({
  CapturePanel: () => <div data-testid="capture-panel" />,
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock('../src/lib/queries', () => ({
  useStateChanges: vi.fn(),
  useActions: vi.fn(),
  useApproveAction: vi.fn(),
  useRejectAction: vi.fn(),
  useTodos: vi.fn(),
  useNeedsJacob: vi.fn(),
  useSnapshotState: vi.fn(),
  useStateNow: vi.fn(),
  useRunInboxTriage: vi.fn(),
  useProjects: vi.fn(),
  useProjectNextSteps: vi.fn(),
  useGatewayHealth: vi.fn(),
  useGatewayModels: vi.fn(),
  useChatsPersistence: vi.fn(),
  useSessionContext: vi.fn(),
  useDeadlines: vi.fn(),
  useDeadlineSweep: vi.fn(),
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
  (useGatewayHealth as Mock).mockReturnValue({
    data: { ok: true, litellmReachable: true, error: null },
    isPending: false,
    isError: false,
    isFetched: true,
  });
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

  it('shows honest empty states when gateway returns no data', () => {
    (useSessionContext as Mock).mockReturnValue({
      data: { current_branch: 'main', last_session_topic: null, open_threads: [], next_actions: [] },
      isPending: false,
      isError: false,
    });
    render(<HomeState />);
    expect(screen.getByText(/not enough signal yet/)).toBeInTheDocument();
    expect(screen.getByText(/no projects registered — \.\/kitty project add/)).toBeInTheDocument();
    expect(screen.getByText('nothing new since last snapshot')).toBeInTheDocument();
    expect(screen.getByText('nothing waiting for you')).toBeInTheDocument();
    expect(screen.getByText('nothing on the list')).toBeInTheDocument();
  });

  // ── health strip ──

  it('shows all-green health strip when everything answers', () => {
    render(<HomeState />);
    expect(screen.getByText('gateway live')).toBeInTheDocument();
    expect(screen.getByText('routing live · 2 models')).toBeInTheDocument();
    expect(screen.getByText('chat store ok · 3 saved')).toBeInTheDocument();
    expect(screen.getByText('retry')).toBeInTheDocument();
  });

  it('shows the ./kitty up fix when the gateway is down', () => {
    (useGatewayHealth as Mock).mockReturnValue({
      data: { ok: false, litellmReachable: false, error: 'Could not reach the gateway' },
      isPending: false,
    });
    render(<HomeState />);
    expect(
      screen.getAllByText(/gateway offline — start it with \.\/kitty up/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText('routing unknown')).toBeInTheDocument();
  });

  it('shows litellm down from the /health probe, never a fake routing-live', () => {
    (useGatewayHealth as Mock).mockReturnValue({
      data: { ok: true, litellmReachable: false, error: null },
      isPending: false,
    });
    render(<HomeState />);
    expect(screen.getByText(/litellm unreachable — \.\/kitty up starts it/)).toBeInTheDocument();
    expect(screen.queryByText(/routing live/)).not.toBeInTheDocument();
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
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: STEP, isPending: false, isError: false },
    ]);
    render(<HomeState />);
    expect(screen.getAllByText('Send the SAID follow-up email').length).toBeGreaterThan(0);
    expect(screen.getByText(/waiting on your approval/)).toBeInTheDocument();
  });

  it('falls back to the freshest project next-step when nothing is proposed', () => {
    (useProjects as Mock).mockReturnValue({ data: [PROJECT], isPending: false, isError: false });
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: STEP, isPending: false, isError: false },
    ]);
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

  it('shows the offline fix in the hero when the gateway is down', () => {
    (useActions as Mock).mockReturnValue({ data: undefined, isPending: false, isError: true });
    render(<HomeState />);
    expect(
      screen.getAllByText(/gateway offline — start it with \.\/kitty up/).length,
    ).toBeGreaterThan(0);
  });

  it("shows an error with a retry button when /session/context fails, not a loading spinner", () => {
    (useSessionContext as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('404 Not Found'),
    });
    render(<HomeState />);
    // Must show an error alert, not a loading spinner
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toMatch(/gateway offline/);
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

  it('shows gateway offline error when actions query fails', () => {
    (useActions as Mock).mockReturnValue({ data: undefined, isPending: false, isError: true });
    render(<HomeState />);
    expect(screen.getByText(/gateway offline — action queue unavailable/)).toBeInTheDocument();
  });

  it('shows gateway offline error when state changes query fails', () => {
    (useStateChanges as Mock).mockReturnValue({ data: undefined, isPending: false, isError: true });
    render(<HomeState />);
    expect(screen.getByText(/gateway offline — changes unavailable/)).toBeInTheDocument();
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

  it("shows an honest error on Today when the gateway is down, not a misleading empty state", () => {
    (useTodos as Mock).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Could not reach the gateway'),
    });
    render(<HomeState />);
    expect(screen.getAllByText(/gateway offline — Could not reach the gateway/).length).toBeGreaterThan(0);
    expect(screen.queryByText('nothing on the list')).not.toBeInTheDocument();
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
    (useProjectNextSteps as Mock).mockReturnValue([
      { data: STEP, isPending: false, isError: false },
    ]);
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

  it('shows an honest offline state for deadlines when the gateway is down', () => {
    (useDeadlines as Mock).mockReturnValue({
      data: { deadlines: [], fromLiveGateway: false, error: 'Could not reach the gateway' },
      isPending: false,
      isError: false,
    });
    render(<HomeState />);
    expect(screen.getByText('gateway offline — deadlines unavailable')).toBeInTheDocument();
  });

  it('runs a sweep from the deadlines card', () => {
    const mutate = vi.fn();
    (useDeadlineSweep as Mock).mockReturnValue({ isPending: false, mutate, data: undefined });
    render(<HomeState />);
    screen.getByText('sweep').click();
    expect(mutate).toHaveBeenCalled();
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
      error: new Error('404 Not Found'),
    });
    render(<HomeState />);
    // The What's Next card must render an alert (its error card) rather than
    // its own loading state (the text "loading…" may still appear in other
    // sections whose queries are pending — that's unrelated).
    const alerts = screen.getAllByRole('alert');
    // At least one alert carries the /session/context error
    const sessionAlert = alerts.find((a) => a.textContent?.includes('404'));
    expect(sessionAlert).toBeTruthy();
    expect(sessionAlert!.textContent).toMatch(/gateway offline/);
    // The error card has a retry button inside the alert
    expect(sessionAlert!.querySelector('button')).toBeTruthy();
    // The What's Next section heading should be visible (proving the section
    // rendered content, not a fallthrough loading … that would hide the heading)
    expect(screen.getByText("what's next")).toBeInTheDocument();
  });
});
