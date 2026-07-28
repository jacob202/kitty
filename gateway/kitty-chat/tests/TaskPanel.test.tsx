import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest';
import type { Mock } from 'vitest';
import { useTasks, useCreateTask, useCancelTask, useTaskOutput } from '../src/lib/queries';
import { TaskPanel } from '../src/components/TaskPanel';

vi.mock('../src/lib/queries', () => ({
  useTasks: vi.fn(),
  useCreateTask: vi.fn(),
  useCancelTask: vi.fn(),
  useTaskOutput: vi.fn(),
}));

const IDLE_MUTATION = { mutate: vi.fn(), isPending: false, isError: false, error: null };

function mockTasks(tasks: unknown[], overrides = {}) {
  (useTasks as Mock).mockReturnValue({ data: tasks, isError: false, error: null, ...overrides });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockTasks([]);
  (useCreateTask as Mock).mockReturnValue({ ...IDLE_MUTATION });
  (useCancelTask as Mock).mockReturnValue({ ...IDLE_MUTATION });
  (useTaskOutput as Mock).mockReturnValue({
    data: undefined, isLoading: false, isError: false, isSuccess: false, error: null,
  });
});

afterEach(cleanup);

describe('TaskPanel feedback', () => {
  it('cancels using the task id the gateway returned', () => {
    const cancel = vi.fn();
    (useCancelTask as Mock).mockReturnValue({ ...IDLE_MUTATION, mutate: cancel });
    mockTasks([{ task_id: 'ab12cd34', goal: 'dig into benefits', task_type: 'research', status: 'queued' }]);

    render(<TaskPanel />);
    fireEvent.click(screen.getByText('cancel'));

    expect(cancel).toHaveBeenCalledWith('ab12cd34');
  });

  it('shows the runner progress line on an active task', () => {
    mockTasks([{
      task_id: 'ab12cd34', goal: 'dig in', task_type: 'research',
      status: 'running', progress: 'Iteration 2...',
    }]);

    render(<TaskPanel />);
    expect(screen.getByText(/Iteration 2/)).toBeInTheDocument();
  });

  it('surfaces a failed launch instead of going quiet', () => {
    (useCreateTask as Mock).mockReturnValue({
      ...IDLE_MUTATION, isError: true, error: new Error('gateway offline'),
    });

    render(<TaskPanel />);
    expect(screen.getByText(/couldn't start that task/)).toBeInTheDocument();
    expect(screen.getByText(/gateway offline/)).toBeInTheDocument();
  });

  it('surfaces a failed cancel instead of going quiet', () => {
    (useCancelTask as Mock).mockReturnValue({
      ...IDLE_MUTATION, isError: true, error: new Error('404 Not Found'),
    });

    render(<TaskPanel />);
    expect(screen.getByText(/couldn't cancel/)).toBeInTheDocument();
  });

  it('shows the error on a failed task', () => {
    mockTasks([{
      task_id: 'ab12cd34', goal: 'orphaned one', task_type: 'research',
      status: 'failed', error: 'orphaned by a gateway restart',
    }]);

    render(<TaskPanel />);
    expect(screen.getByText(/orphaned by a gateway restart/)).toBeInTheDocument();
  });

  it('reveals task output on demand', () => {
    mockTasks([{ task_id: 'ab12cd34', goal: 'done one', task_type: 'research', status: 'completed' }]);
    (useTaskOutput as Mock).mockReturnValue({
      data: 'the research findings', isLoading: false, isError: false, isSuccess: true, error: null,
    });

    render(<TaskPanel />);
    expect(screen.queryByText('the research findings')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('show output'));
    expect(screen.getByText('the research findings')).toBeInTheDocument();
  });

  it('says so when a finished task wrote nothing', () => {
    mockTasks([{ task_id: 'ab12cd34', goal: 'quiet one', task_type: 'cleanup', status: 'completed' }]);
    (useTaskOutput as Mock).mockReturnValue({
      data: '', isLoading: false, isError: false, isSuccess: true, error: null,
    });

    render(<TaskPanel />);
    fireEvent.click(screen.getByText('show output'));
    expect(screen.getByText(/wrote no output/)).toBeInTheDocument();
  });

  it('reports an unreadable task list', () => {
    mockTasks([], { isError: true, error: new Error('503 Service Unavailable') });

    render(<TaskPanel />);
    expect(screen.getByText(/can't read the task list/)).toBeInTheDocument();
  });
});
