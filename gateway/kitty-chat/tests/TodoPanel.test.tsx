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
    vi.mocked(queries.useTodos).mockReturnValue({ data: [{ id: 7, content: 'ship it', status: 'pending' }], isPending: false } as never)
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
    fireEvent.change(screen.getByPlaceholderText('add a todo…'), { target: { value: 'new item' } })
    fireEvent.click(screen.getByRole('button', { name: 'add' }))
    expect(add).toHaveBeenCalledWith('new item', expect.any(Object))
  })
})
