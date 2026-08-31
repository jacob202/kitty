import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TodoPanel } from '../src/components/TodoPanel'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => ({
  ...(await vi.importActual<typeof queries>('../src/lib/queries')),
  useTodos: vi.fn(), useAddTodo: vi.fn(), useCompleteTodo: vi.fn(), useDeleteTodo: vi.fn(),
}))

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><TodoPanel /></QueryClientProvider>)
}

describe('TodoPanel', () => {
  beforeEach(() => {
    vi.mocked(queries.useTodos).mockReturnValue({ data: [{ id: 7, content: 'ship it', status: 'pending' }], isPending: false, isError: false } as never)
    vi.mocked(queries.useCompleteTodo).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
    vi.mocked(queries.useAddTodo).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
    vi.mocked(queries.useDeleteTodo).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
  })
  afterEach(cleanup)

  it('completes a backend-shaped pending todo by numeric id', async () => {
    const complete = vi.fn()
    vi.mocked(queries.useCompleteTodo).mockReturnValue({ mutate: complete, isPending: false } as never)
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /complete/i }))
    await waitFor(() => expect(complete).toHaveBeenCalledWith(7))
  })

  it('keeps the add control usable', () => {
    const add = vi.fn()
    vi.mocked(queries.useAddTodo).mockReturnValue({ mutate: add, isPending: false } as never)
    renderPanel()
    fireEvent.change(screen.getByRole('textbox', { name: 'Add a todo' }), { target: { value: 'new item' } })
    fireEvent.click(screen.getByRole('button', { name: 'add' }))
    expect(add).toHaveBeenCalledWith('new item', expect.any(Object))
  })

  it('shows a friendly load failure and retries', () => {
    const refetch = vi.fn()
    vi.mocked(queries.useTodos).mockReturnValue({ data: undefined, isPending: false, isError: true, refetch } as never)
    renderPanel()
    expect(screen.getByText(/todos are unavailable/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /retry todos/i }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('shows a friendly loading state', () => {
    vi.mocked(queries.useTodos).mockReturnValue({ data: undefined, isPending: true, isError: false } as never)
    renderPanel()
    expect(screen.getByText('loading todos…')).toBeInTheDocument()
  })

  it('shows a friendly completion failure', () => {
    vi.mocked(queries.useCompleteTodo).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: true } as never)
    renderPanel()
    expect(screen.getByText(/couldn't complete todo/i)).toBeInTheDocument()
  })

  it('clears all completed todos by calling delete for each', async () => {
    const deleteTodo = vi.fn()
    const deleteTodoAsync = vi.fn().mockResolvedValue(undefined)
    vi.mocked(queries.useTodos).mockReturnValue({
      data: [
        { id: 1, content: 'done 1', status: 'completed' },
        { id: 2, content: 'done 2', status: 'completed' },
        { id: 3, content: 'active', status: 'pending' },
      ],
      isPending: false,
      isError: false,
    } as never)
    vi.mocked(queries.useDeleteTodo).mockReturnValue({ mutate: deleteTodo, mutateAsync: deleteTodoAsync, isPending: false } as never)
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /clear done/i }))
    await waitFor(() => expect(deleteTodoAsync).toHaveBeenCalledTimes(2))
    expect(deleteTodoAsync).toHaveBeenCalledWith(1)
    expect(deleteTodoAsync).toHaveBeenCalledWith(2)
  })

  it('shows error when any clear-done deletion fails', async () => {
    const deleteTodo = vi.fn()
    const deleteTodoAsync = vi.fn()
      .mockImplementationOnce(() => Promise.resolve()) // first succeeds
      .mockImplementationOnce(() => Promise.reject(new Error('delete failed'))) // second fails
    vi.mocked(queries.useTodos).mockReturnValue({
      data: [
        { id: 1, content: 'done 1', status: 'completed' },
        { id: 2, content: 'done 2', status: 'completed' },
      ],
      isPending: false,
      isError: false,
    } as never)
    vi.mocked(queries.useDeleteTodo).mockReturnValue({ mutate: deleteTodo, mutateAsync: deleteTodoAsync, isPending: false, isError: false } as never)
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /clear done/i }))
    await waitFor(() => expect(screen.getByText(/couldn't clear completed todos/i)).toBeInTheDocument())
  })
})
