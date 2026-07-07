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
  useGatewayWeather,
  useKnowledgeSources,
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
  useGatewayWeather: vi.fn(),
  useKnowledgeSources: vi.fn(),
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
  (useGatewayWeather as Mock).mockReturnValue({
    data: { weather: { temp: 72, condition: 'Clear' }, ok: true },
    isPending: false,
    isError: false,
    isFetched: true,
  });
  (useKnowledgeSources as Mock).mockReturnValue({
    data: { sources: [] },
    isPending: false,
    isError: false,
    isFetched: true,
  });
}

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

  it('shows the offline fix in the hero when the gateway is down', () => {
    (useActions as Mock).mockReturnValue({ data: undefined, isPending: false, isError: true });
    render(<HomeState />);
    expect(
      screen.getAllByText(/gateway offline — start it with \.\/kitty up/).length,
    ).toBeGreaterThan(0);
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
    render(<HomeState gatewayError="Could not reach the gateway" />);
    expect(screen.getByText(/gateway offline — Could not reach the gateway/)).toBeInTheDocument();
    expect(screen.queryByText('nothing on the list')).not.toBeInTheDocument();
  });
});
