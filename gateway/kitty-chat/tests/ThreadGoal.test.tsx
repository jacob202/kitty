import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest'
import { ThreadGoal } from '../src/components/ThreadGoal'
import * as gateway from '../src/lib/gateway'
import type { Chat } from '../src/lib/types'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    patchChatObjective: vi.fn(),
  }
})

const patchChatObjective = vi.mocked(gateway.patchChatObjective)

function makeChat(overrides: Partial<Chat> = {}): Chat {
  return {
    id: 'chat-1',
    title: 'First Chat',
    messages: [],
    model: 'kitty-default',
    color: 'teal',
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  }
}

function renderGoal(chat: Chat | null, overrides: {
  onObjectiveSaved?: (chatId: string, objective: string | null) => void
  onEnsurePersisted?: (chat: Chat) => Promise<boolean>
} = {}) {
  const onObjectiveSaved = overrides.onObjectiveSaved ?? vi.fn()
  const onEnsurePersisted = overrides.onEnsurePersisted ?? vi.fn(async () => true)
  const utils = render(
    <ThreadGoal
      chat={chat}
      onObjectiveSaved={onObjectiveSaved}
      onEnsurePersisted={onEnsurePersisted}
    />,
  )
  return { ...utils, onObjectiveSaved, onEnsurePersisted }
}

function rerenderGoal(
  utils: ReturnType<typeof renderGoal>,
  chat: Chat | null,
) {
  utils.rerender(
    <ThreadGoal
      chat={chat}
      onObjectiveSaved={utils.onObjectiveSaved}
      onEnsurePersisted={utils.onEnsurePersisted}
    />,
  )
}

describe('ThreadGoal', () => {
  beforeEach(() => {
    patchChatObjective.mockReset()
  })
  afterEach(cleanup)

  it('renders nothing without an active chat', () => {
    const { container } = renderGoal(null)
    expect(container).toBeEmptyDOMElement()
  })

  it('offers setting a goal when the chat has none', () => {
    renderGoal(makeChat())
    expect(screen.getByRole('button', { name: 'Set thread goal' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Thread goal')).not.toBeInTheDocument()
  })

  it('shows the goal when set', () => {
    renderGoal(makeChat({ objective: 'ship the resume' }))
    expect(screen.getByText('ship the resume')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Edit thread goal/ })).toBeInTheDocument()
  })

  it('sets a goal, trimming whitespace and reflecting the server value', async () => {
    patchChatObjective.mockResolvedValue({ objective: 'ship the resume' })
    const { onObjectiveSaved } = renderGoal(makeChat())

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.change(screen.getByLabelText('Thread goal'), {
      target: { value: '  ship the resume  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    await waitFor(() => {
      expect(onObjectiveSaved).toHaveBeenCalledWith('chat-1', 'ship the resume')
    })
    expect(patchChatObjective).toHaveBeenCalledWith('chat-1', 'ship the resume')
    // Editor closed again after a confirmed save.
    expect(screen.queryByLabelText('Thread goal')).not.toBeInTheDocument()
  })

  it('edits an existing goal, prefilled with the current value', async () => {
    patchChatObjective.mockResolvedValue({ objective: 'find a job' })
    const { onObjectiveSaved } = renderGoal(makeChat({ objective: 'ship the resume' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    const textarea = screen.getByLabelText('Thread goal')
    expect(textarea).toHaveValue('ship the resume')

    fireEvent.change(textarea, { target: { value: 'find a job' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    await waitFor(() => {
      expect(onObjectiveSaved).toHaveBeenCalledWith('chat-1', 'find a job')
    })
    expect(patchChatObjective).toHaveBeenCalledWith('chat-1', 'find a job')
  })

  it('clears the goal via the clear button', async () => {
    patchChatObjective.mockResolvedValue({ objective: null })
    const { onObjectiveSaved } = renderGoal(makeChat({ objective: 'ship the resume' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear thread goal' }))

    await waitFor(() => {
      expect(onObjectiveSaved).toHaveBeenCalledWith('chat-1', null)
    })
    expect(patchChatObjective).toHaveBeenCalledWith('chat-1', null)
  })

  it('treats a whitespace-only submission over an existing goal as clearing', async () => {
    patchChatObjective.mockResolvedValue({ objective: null })
    renderGoal(makeChat({ objective: 'ship the resume' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    await waitFor(() => {
      expect(patchChatObjective).toHaveBeenCalledWith('chat-1', null)
    })
  })

  it('does not offer a clear button when there is no goal to clear', () => {
    renderGoal(makeChat())
    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    expect(screen.queryByRole('button', { name: 'Clear thread goal' })).not.toBeInTheDocument()
  })

  it('cancels without saving and keeps the previous goal', () => {
    renderGoal(makeChat({ objective: 'ship the resume' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'abandoned draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel goal edit' }))

    expect(patchChatObjective).not.toHaveBeenCalled()
    expect(screen.getByText('ship the resume')).toBeInTheDocument()
  })

  it('saves on Enter and cancels on Escape', async () => {
    patchChatObjective.mockResolvedValue({ objective: 'via keyboard' })
    const { onObjectiveSaved } = renderGoal(makeChat())

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.keyDown(screen.getByLabelText('Thread goal'), { key: 'Escape' })
    expect(screen.queryByLabelText('Thread goal')).not.toBeInTheDocument()
    expect(patchChatObjective).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'via keyboard' } })
    fireEvent.keyDown(screen.getByLabelText('Thread goal'), { key: 'Enter' })

    await waitFor(() => {
      expect(onObjectiveSaved).toHaveBeenCalledWith('chat-1', 'via keyboard')
    })
  })

  it('closes without a request when the submitted value is unchanged', () => {
    renderGoal(makeChat({ objective: 'ship the resume' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    expect(patchChatObjective).not.toHaveBeenCalled()
    expect(screen.getByText('ship the resume')).toBeInTheDocument()
  })

  it('keeps the editor open and reports the error when persistence fails', async () => {
    patchChatObjective.mockRejectedValue(new Error('Gateway returned 400 Bad Request'))
    const { onObjectiveSaved } = renderGoal(makeChat({ objective: 'old goal' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'new goal' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Gateway returned 400 Bad Request')
    expect(onObjectiveSaved).not.toHaveBeenCalled()
    // Draft survives so the attempt can be retried or corrected.
    expect(screen.getByLabelText('Thread goal')).toHaveValue('new goal')
  })

  it('blocks repeated taps while a save is in flight', async () => {
    let resolvePatch: (v: { objective: string | null }) => void = () => {}
    patchChatObjective.mockImplementation(
      () => new Promise((resolve) => { resolvePatch = resolve }),
    )
    renderGoal(makeChat())

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'one save only' } })
    const saveBtn = screen.getByRole('button', { name: 'Save thread goal' })
    fireEvent.click(saveBtn)
    fireEvent.click(saveBtn)
    fireEvent.click(saveBtn)

    expect(patchChatObjective).toHaveBeenCalledTimes(1)
    expect(saveBtn).toBeDisabled()
    expect(saveBtn).toHaveTextContent('saving…')

    resolvePatch({ objective: 'one save only' })
    await waitFor(() => {
      expect(screen.queryByLabelText('Thread goal')).not.toBeInTheDocument()
    })
  })

  it('persists a never-saved chat first when the PATCH 404s, then retries', async () => {
    patchChatObjective
      .mockRejectedValueOnce(new Error('Gateway returned 404 Not Found'))
      .mockResolvedValueOnce({ objective: 'fresh chat goal' })
    const chat = makeChat()
    const { onObjectiveSaved, onEnsurePersisted } = renderGoal(chat)

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.change(screen.getByLabelText('Thread goal'), {
      target: { value: 'fresh chat goal' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    await waitFor(() => {
      expect(onObjectiveSaved).toHaveBeenCalledWith('chat-1', 'fresh chat goal')
    })
    expect(onEnsurePersisted).toHaveBeenCalledWith(chat)
    expect(patchChatObjective).toHaveBeenCalledTimes(2)
  })

  it('surfaces the failure when the 404 recovery persist also fails', async () => {
    patchChatObjective.mockRejectedValue(new Error('Gateway returned 404 Not Found'))
    const { onObjectiveSaved } = renderGoal(makeChat(), {
      onEnsurePersisted: vi.fn(async () => false),
    })

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'doomed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('404')
    expect(patchChatObjective).toHaveBeenCalledTimes(1)
    expect(onObjectiveSaved).not.toHaveBeenCalled()
  })

  it('drops the draft and shows the new thread goal when the active chat switches', () => {
    const utils = renderGoal(makeChat({ objective: 'goal one' }))

    fireEvent.click(screen.getByRole('button', { name: /Edit thread goal/ }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'half-typed' } })

    rerenderGoal(utils, makeChat({ id: 'chat-2', objective: 'goal two' }))

    expect(screen.queryByLabelText('Thread goal')).not.toBeInTheDocument()
    expect(screen.getByText('goal two')).toBeInTheDocument()
    expect(patchChatObjective).not.toHaveBeenCalled()
  })

  it('still records a late save against the right chat after switching threads', async () => {
    let resolvePatch: (v: { objective: string | null }) => void = () => {}
    patchChatObjective.mockImplementation(
      () => new Promise((resolve) => { resolvePatch = resolve }),
    )
    const utils = renderGoal(makeChat())

    fireEvent.click(screen.getByRole('button', { name: 'Set thread goal' }))
    fireEvent.change(screen.getByLabelText('Thread goal'), { target: { value: 'late arrival' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save thread goal' }))

    // Thread switches while the PATCH is still in flight.
    rerenderGoal(utils, makeChat({ id: 'chat-2' }))
    resolvePatch({ objective: 'late arrival' })

    await waitFor(() => {
      expect(utils.onObjectiveSaved).toHaveBeenCalledWith('chat-1', 'late arrival')
    })
    // The new thread's UI is untouched: still resting, still goalless.
    expect(screen.getByRole('button', { name: 'Set thread goal' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Thread goal')).not.toBeInTheDocument()
  })
})
