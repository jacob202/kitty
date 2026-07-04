import { render, screen, cleanup } from '@testing-library/react';
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import {
  useStateChanges,
  useActions,
  useApproveAction,
  useRejectAction,
  useTodos,
  useLoops,
  useNeedsJacob,
} from '../src/lib/queries';
import { HomeState } from '../src/components/HomeState';

vi.mock('../src/components/CapturePanel', () => ({
  CapturePanel: () => <div data-testid="capture-panel" />,
}));

vi.mock('../src/lib/queries', () => ({
  useStateChanges: vi.fn(),
  useActions: vi.fn(),
  useApproveAction: vi.fn(),
  useRejectAction: vi.fn(),
  useTodos: vi.fn(),
  useLoops: vi.fn(),
  useNeedsJacob: vi.fn(),
}));

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
  (useLoops as Mock).mockReturnValue({
    data: { loops: [], fromLiveGateway: true, error: null },
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
}

describe('HomeState', () => {
  beforeEach(setDefaultMocks);
  afterEach(cleanup);

  it('renders all five section titles', () => {
    render(<HomeState />);
    expect(screen.getByText('what changed')).toBeInTheDocument();
    expect(screen.getByText('needs you')).toBeInTheDocument();
    expect(screen.getByText('open loops')).toBeInTheDocument();
    expect(screen.getByText('today')).toBeInTheDocument();
    expect(screen.getByText('capture')).toBeInTheDocument();
  });

  it('shows empty states when gateway returns no data', () => {
    render(<HomeState />);
    expect(screen.getByText('nothing new since last snapshot')).toBeInTheDocument();
    expect(screen.getByText('nothing waiting for you')).toBeInTheDocument();
    expect(screen.getByText('no open loops')).toBeInTheDocument();
    expect(screen.getByText('nothing on the list')).toBeInTheDocument();
  });

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

  it('shows proposed actions with approve and reject buttons', () => {
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
    expect(screen.getByText('Deploy to prod')).toBeInTheDocument();
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
    expect(screen.getByText('write tests')).toBeInTheDocument();
    expect(screen.getByText('in flight')).toBeInTheDocument();
    expect(screen.queryByText('done already')).not.toBeInTheDocument();
  });

  it('applies compact padding when compact prop is true', () => {
    const { container } = render(<HomeState compact />);
    const grid = container.firstChild as HTMLElement;
    expect(grid.style.padding).toBe('16px 12px 40px');
  });
});
