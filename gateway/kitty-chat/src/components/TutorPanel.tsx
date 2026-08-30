'use client'
import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  askTutor,
  fetchTutorQuiz,
  postTutorAttempt,
  type TutorAnswer,
  type TutorQuizQuestion,
} from '@/lib/gateway'

/** Split a canonical "A: body" option into its label and body. */
function splitOption(option: string): { label: string; body: string } {
  const idx = option.indexOf(': ')
  if (idx === -1) return { label: option, body: option }
  return { label: option.slice(0, idx), body: option.slice(idx + 2) }
}

type CardResult = { picked: string; correct: boolean; mastery?: number; stage?: string }

function QuizCard({ q }: { q: TutorQuizQuestion }) {
  const [result, setResult] = useState<CardResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const answerBody = splitOption(
    q.options.find((o) => splitOption(o).label === q.answer_label) ?? '',
  ).body

  const pick = async (option: string) => {
    if (result) return
    const { label } = splitOption(option)
    const correct = label === q.answer_label
    setResult({ picked: label, correct })
    try {
      // The graded term is the correct answer's body — that's the knowledge
      // point whose mastery this attempt proves or dents.
      const attempt = await postTutorAttempt(answerBody, correct)
      setResult({ picked: label, correct, mastery: attempt.mastery, stage: attempt.stage })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div style={cardStyle}>
      <div style={questionStyle}>{q.question}</div>
      <div style={{ display: 'grid', gap: 5 }}>
        {q.options.map((option) => {
          const { label, body } = splitOption(option)
          const isPicked = result?.picked === label
          const isAnswer = label === q.answer_label
          const showState = result !== null
          return (
            <button
              key={label}
              onClick={() => void pick(option)}
              disabled={result !== null}
              style={{
                ...optionStyle,
                ...(showState && isAnswer ? { borderColor: 'var(--c-green, #9be86b)', color: 'var(--ink)' } : {}),
                ...(showState && isPicked && !isAnswer ? { borderColor: 'var(--c-red)', color: 'var(--c-red)' } : {}),
                cursor: result ? 'default' : 'pointer',
              }}
            >
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, marginRight: 8 }}>{label}</span>
              {body}
            </button>
          )
        })}
      </div>
      {result && (
        <div style={resultLineStyle}>
          {result.correct ? 'got it' : `nope — ${q.answer_label}: ${answerBody}`}
          {result.mastery !== undefined && (
            <span style={{ color: 'var(--ink-2)' }}>
              {' '}· mastery {(result.mastery * 100).toFixed(0)}% · {result.stage}
            </span>
          )}
        </div>
      )}
      {error && (
        <div role="alert" style={{ ...resultLineStyle, color: 'var(--c-red)' }}>
          attempt not recorded — {error}
        </div>
      )}
    </div>
  )
}

export function TutorPanel() {
  const queryClient = useQueryClient()
  const quizQuery = useQuery({
    queryKey: ['tutor', 'quiz'],
    queryFn: () => fetchTutorQuiz(),
    refetchOnWindowFocus: false,
  })

  const [topic, setTopic] = useState('')
  const [asking, setAsking] = useState(false)
  const [answer, setAnswer] = useState<TutorAnswer | null>(null)
  const [askError, setAskError] = useState<string | null>(null)

  const ask = async () => {
    const trimmed = topic.trim()
    if (!trimmed || asking) return
    setAsking(true)
    setAskError(null)
    setAnswer(null)
    try {
      setAnswer(await askTutor(trimmed))
    } catch (err) {
      setAskError(err instanceof Error ? err.message : String(err))
    } finally {
      setAsking(false)
    }
  }

  const quiz = quizQuery.data

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <section style={{ display: 'grid', gap: 8 }}>
        <div style={sectionHeadStyle}>ask</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void ask()}
            placeholder="what do you want to understand?"
            style={askInputStyle}
          />
          <button onClick={() => void ask()} disabled={asking || !topic.trim()} style={askBtnStyle}>
            {asking ? '…' : 'ask'}
          </button>
        </div>
        {askError && (
          <p role="alert" style={{ ...mutedStyle, color: 'var(--c-red)' }}>{askError}</p>
        )}
        {answer && (
          <div style={cardStyle}>
            {answer.vocab.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {answer.vocab.map((v) => (
                  <span key={v} style={vocabChipStyle}>{v}</span>
                ))}
              </div>
            )}
            <p style={{ ...bodyTextStyle, margin: 0 }}>{answer.explain}</p>
            <p style={{ ...bodyTextStyle, margin: 0, color: 'var(--ink-2)' }}>↳ {answer.question}</p>
          </div>
        )}
      </section>

      <section style={{ display: 'grid', gap: 8 }}>
        <div style={sectionHeadStyle}>
          review
          {quiz && quiz.due > 0 && (
            <span style={{ color: 'var(--primary)' }}> · {quiz.due} due</span>
          )}
          <button
            onClick={() => void queryClient.invalidateQueries({ queryKey: ['tutor', 'quiz'] })}
            style={refreshStyle}
            title="new quiz"
          >
            ↻
          </button>
        </div>
        {quizQuery.isLoading ? (
          <p style={mutedStyle}>loading…</p>
        ) : quizQuery.isError ? (
          <p role="alert" style={{ ...mutedStyle, color: 'var(--c-red)' }}>
            quiz unavailable — {quizQuery.error instanceof Error ? quizQuery.error.message : 'gateway error'}
          </p>
        ) : quiz && quiz.questions.length > 0 ? (
          quiz.questions.map((q) => <QuizCard key={q.question} q={q} />)
        ) : (
          <p style={mutedStyle}>
            nothing due for review{quiz && quiz.due === 1 ? ' (1 term due, quizzes need 2+)' : ''}
          </p>
        )}
      </section>
    </div>
  )
}

const sectionHeadStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
  letterSpacing: '0.12em', textTransform: 'lowercase', color: 'var(--ink-2)',
  display: 'flex', alignItems: 'center', gap: 4,
}
const cardStyle: CSSProperties = {
  display: 'grid', gap: 8, padding: 12,
  background: 'var(--surface)', border: '1.5px solid var(--line)', borderRadius: 12,
}
const questionStyle: CSSProperties = {
  fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, color: 'var(--ink)',
}
const optionStyle: CSSProperties = {
  textAlign: 'left', fontFamily: 'var(--font-body)', fontSize: 12,
  color: 'var(--ink-2)', background: 'transparent',
  border: '1.5px solid var(--line)', borderRadius: 8, padding: '8px 10px',
  minHeight: 34,
}
const resultLineStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink)',
}
const mutedStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)', margin: 0,
}
const bodyTextStyle: CSSProperties = {
  fontFamily: 'var(--font-body)', fontSize: 13, lineHeight: 1.5, color: 'var(--ink)',
}
const vocabChipStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--primary)',
  border: '1px solid var(--line)', borderRadius: 99, padding: '2px 9px',
}
const askInputStyle: CSSProperties = {
  flex: 1, fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--ink)',
  background: 'var(--surface)', border: '1.5px solid var(--line)',
  borderRadius: 10, padding: '8px 12px', outline: 'none',
}
const askBtnStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink)',
  background: 'transparent', border: '1.5px solid var(--ink-2)',
  borderRadius: 10, padding: '8px 16px', cursor: 'pointer',
}
const refreshStyle: CSSProperties = {
  marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12,
  color: 'var(--ink-2)', background: 'transparent', border: 'none', cursor: 'pointer',
}
