import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { TutorPanel } from '../src/components/TutorPanel'

const fetchTutorQuiz = vi.hoisted(() => vi.fn())
const postTutorAttempt = vi.hoisted(() => vi.fn())
const askTutor = vi.hoisted(() => vi.fn())
vi.mock('../src/lib/gateway', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  fetchTutorQuiz,
  postTutorAttempt,
  askTutor,
}))

const QUIZ = {
  due: 2,
  questions: [
    {
      question: 'What does alpha mean?',
      options: ['A: alpha', 'B: beta'],
      answer_label: 'A',
    },
  ],
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <TutorPanel />
    </QueryClientProvider>,
  )
}

describe('TutorPanel', () => {
  beforeEach(() => {
    fetchTutorQuiz.mockReset().mockResolvedValue(QUIZ)
    postTutorAttempt.mockReset().mockResolvedValue({
      term: 'alpha', mastery: 0.5, stage: 'learning', next_action: 'practice',
    })
    askTutor.mockReset()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders due count and quiz questions', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('What does alpha mean?')).toBeInTheDocument())
    expect(screen.getByText(/2 due/)).toBeInTheDocument()
  })

  it('picking the right option records a correct attempt and shows mastery', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('What does alpha mean?')).toBeInTheDocument())
    fireEvent.click(screen.getByText('alpha'))
    await waitFor(() =>
      expect(postTutorAttempt).toHaveBeenCalledExactlyOnceWith('alpha', true),
    )
    await waitFor(() => expect(screen.getByText(/mastery 50%/)).toBeInTheDocument())
  })

  it('picking a wrong option records an incorrect attempt and reveals the answer', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('What does alpha mean?')).toBeInTheDocument())
    fireEvent.click(screen.getByText('beta'))
    await waitFor(() =>
      expect(postTutorAttempt).toHaveBeenCalledExactlyOnceWith('alpha', false),
    )
    expect(screen.getByText(/nope — A: alpha/)).toBeInTheDocument()
  })

  it('asks the tutor and renders vocab-first answers', async () => {
    askTutor.mockResolvedValue({
      vocab: ['refactor'],
      explain: 'like reorganizing a toolbox.',
      question: 'why keep behavior fixed?',
    })
    renderPanel()
    fireEvent.change(screen.getByPlaceholderText('what do you want to understand?'), {
      target: { value: 'refactoring' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'ask' }))
    await waitFor(() => expect(screen.getByText('like reorganizing a toolbox.')).toBeInTheDocument())
    expect(screen.getByText('refactor')).toBeInTheDocument()
  })
})
