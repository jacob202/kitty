'use client'
import { useState, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  askTutor,
  fetchTutorQuiz,
  fetchTutorReview,
  postTutorAttempt,
  tutorLearn,
  type TutorAnswer,
  type TutorQuizQuestion,
  type TutorReviewItem,
} from '@/lib/gateway'

const TABS = ['quiz', 'learn', 'review'] as const
type Tab = (typeof TABS)[number]

function QuizTab() {
  const [answer, setAnswer] = useState('')
  const [askResult, setAskResult] = useState<TutorAnswer | null>(null)
  const [askError, setAskError] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)

  const quiz = useQuery({
    queryKey: ['tutor-quiz'],
    queryFn: () => fetchTutorQuiz(5),
    refetchOnWindowFocus: false,
  })

  const handleAsk = async () => {
    if (!answer.trim() || asking) return
    setAsking(true)
    setAskError(null)
    try {
      const result = await askTutor(answer.trim())
      setAskResult(result)
    } catch (err) {
      setAskError(err instanceof Error ? err.message : String(err))
    } finally {
      setAsking(false)
    }
  }

  if (quiz.isLoading) return <div style={loadingStyle}>loading quiz...</div>
  if (quiz.error) return <div style={errorStyle}>quiz failed: {String(quiz.error)}</div>

  const { questions, due } = quiz.data ?? { questions: [], due: 0 }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={statStyle}>
        <span>due for review: <strong>{due}</strong></span>
      </div>

      {askResult && (
        <div style={answerCardStyle}>
          <div style={vocabStyle}>{askResult.explain}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--ink)', marginTop: 8 }}>
            {askResult.question}
          </div>
        </div>
      )}
      {askError && <div style={errorStyle}>{askError}</div>}

      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAsk() }}
          placeholder="ask anything..."
          style={inputStyle}
        />
        <button onClick={handleAsk} disabled={asking} style={askBtnStyle}>
          {asking ? '...' : 'ask'}
        </button>
      </div>

      {questions.map((q, i) => (
        <QuizCard key={i} q={q} />
      ))}
    </div>
  )
}

function QuizCard({ q }: { q: TutorQuizQuestion }) {
  const [result, setResult] = useState<{ picked: string; correct: boolean; mastery?: number; stage?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  const answerBody = q.options.find((o) => {
    const idx = o.indexOf(': ')
    return idx !== -1 && o.slice(0, idx) === q.answer_label
  })?.split(': ').slice(1).join(': ') ?? ''

  const pick = async (option: string) => {
    if (result) return
    const idx = option.indexOf(': ')
    const label = idx !== -1 ? option.slice(0, idx) : option
    const correct = label === q.answer_label
    setResult({ picked: label, correct })
    try {
      const attempt = await postTutorAttempt(answerBody, correct)
      setResult({ picked: label, correct, mastery: attempt.mastery, stage: attempt.stage })
      qc.invalidateQueries({ queryKey: ['tutor-quiz'] })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div style={cardStyle}>
      <div style={questionStyle}>{q.question}</div>
      <div style={{ display: 'grid', gap: 5 }}>
        {q.options.map((option) => {
          const idx = option.indexOf(': ')
          const label = idx !== -1 ? option.slice(0, idx) : option
          const body = idx !== -1 ? option.slice(idx + 2) : option
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
                ...(showState && isAnswer ? { borderColor: 'var(--c-green)', color: 'var(--ink)' } : {}),
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
      {error && <div style={errorStyle}>{error}</div>}
    </div>
  )
}

function LearnTab() {
  const [path, setPath] = useState('')
  const [label, setLabel] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const qc = useQueryClient()

  const handleLearn = async () => {
    if (!path.trim() || loading) return
    setLoading(true)
    setError(null)
    setStatus(null)
    try {
      const result = await tutorLearn(path.trim(), label.trim() || undefined)
      setStatus(`ingested ${result.ingested} chunks — ${result.status}`)
      qc.invalidateQueries({ queryKey: ['tutor-quiz'] })
      qc.invalidateQueries({ queryKey: ['tutor-review'] })
      setPath('')
      setLabel('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.6 }}>
        paste a file path or document to learn from. kitty will index it and build quiz questions.
      </div>
      <input
        value={path}
        onChange={(e) => setPath(e.target.value)}
        placeholder="file path (e.g. /Users/jacob/docs/notes.md)"
        style={inputStyle}
      />
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="optional label"
        style={{ ...inputStyle, width: '50%' }}
      />
      <button onClick={handleLearn} disabled={loading || !path.trim()} style={learnBtnStyle}>
        {loading ? 'ingesting...' : 'learn'}
      </button>
      {status && <div style={{ ...statStyle, color: 'var(--c-green)' }}>{status}</div>}
      {error && <div style={errorStyle}>{error}</div>}
    </div>
  )
}

function ReviewTab() {
  const review = useQuery({
    queryKey: ['tutor-review'],
    queryFn: fetchTutorReview,
    refetchOnWindowFocus: false,
  })

  if (review.isLoading) return <div style={loadingStyle}>loading review...</div>
  if (review.error) return <div style={errorStyle}>review failed: {String(review.error)}</div>

  const { due } = review.data ?? { due: [] }

  if (!due.length) {
    return <div style={statStyle}>nothing due for review. nice.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={statStyle}>{due.length} term{due.length !== 1 ? 's' : ''} due for review</div>
      {due.map((item: TutorReviewItem) => (
        <div key={item.term} style={{ ...cardStyle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--ink)', fontWeight: 600 }}>
              {item.term}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)', marginTop: 4 }}>
              {item.knowledge_type} · confidence {item.confidence} · {item.stage}
            </div>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}>
            last seen {item.last_seen ? new Date(item.last_seen).toLocaleDateString() : 'never'}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function TutorShell({ isMobile }: { isMobile: boolean }) {
  const [tab, setTab] = useState<Tab>('quiz')
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div style={{ flex: 1, padding: pad, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1.5px solid var(--line)', paddingBottom: 0 }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 16px', border: 'none', background: tab === t ? 'var(--ginger-fade)' : 'transparent',
              color: tab === t ? 'var(--cat-ginger)' : 'var(--ink-2)',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              borderBottom: tab === t ? '2px solid var(--cat-ginger)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === 'quiz' && <QuizTab />}
      {tab === 'learn' && <LearnTab />}
      {tab === 'review' && <ReviewTab />}
    </div>
  )
}

const statStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-2)',
  padding: '8px 12px', background: 'var(--surface)', borderRadius: 8,
}
const loadingStyle: React.CSSProperties = { padding: 16, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-2)' }
const errorStyle: React.CSSProperties = { padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--c-red)', background: 'var(--surface)', borderRadius: 8 }
const cardStyle: React.CSSProperties = { padding: 14, background: 'var(--surface)', borderRadius: 12, border: '1.5px solid var(--line)' }
const questionStyle: React.CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--ink)', marginBottom: 12, lineHeight: 1.5 }
const optionStyle: React.CSSProperties = { padding: '10px 14px', background: 'var(--bg)', border: '1.5px solid var(--line)', borderRadius: 8, fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--ink)', textAlign: 'left' as const }
const resultLineStyle: React.CSSProperties = { marginTop: 10, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }
const answerCardStyle: React.CSSProperties = { ...cardStyle, borderColor: 'var(--primary)' }
const vocabStyle: React.CSSProperties = { fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--ink)', lineHeight: 1.6 }
const inputStyle: React.CSSProperties = { width: '100%', padding: '10px 14px', background: 'var(--surface)', border: '1.5px solid var(--line)', borderRadius: 10, fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--ink)', outline: 'none' }
const askBtnStyle: React.CSSProperties = { padding: '10px 20px', background: 'var(--primary)', color: 'var(--on-primary)', border: 'none', borderRadius: 10, fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, cursor: 'pointer', flexShrink: 0 }
const learnBtnStyle: React.CSSProperties = { padding: '10px 20px', background: 'var(--primary)', color: 'var(--on-primary)', border: 'none', borderRadius: 10, fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-start' }
