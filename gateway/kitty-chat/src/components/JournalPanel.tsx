'use client'
import { useState, useRef, useEffect } from 'react'
import type { CSSProperties } from 'react'

type JournalState = 'idle' | 'interviewing' | 'synthesizing' | 'done'

interface JMsg { role: 'user' | 'assistant'; content: string }

const THEMES = ['reflection', 'work', 'mood', 'recovery', 'relationships', 'body', 'creative']

export function JournalPanel() {
  const [state, setState] = useState<JournalState>('idle')
  const [theme, setTheme] = useState('reflection')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [sessionTheme, setSessionTheme] = useState('')
  const [messages, setMessages] = useState<JMsg[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [entry, setEntry] = useState('')
  const sessionId = useRef(`j-${Date.now()}`)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleStart() {
    setThinking(true)
    try {
      const res = await fetch(`/proxy/journal/start?theme=${theme}`, { method: 'POST' })
      const data = await res.json() as { opener: string; system_prompt: string; theme: string }
      setSystemPrompt(data.system_prompt)
      setSessionTheme(data.theme)
      setMessages([{ role: 'assistant', content: data.opener }])
      setState('interviewing')
    } finally {
      setThinking(false)
    }
  }

  async function handleReply() {
    const text = input.trim()
    if (!text || thinking) return
    const userMsg: JMsg = { role: 'user', content: text }
    const next = [...messages, userMsg]
    setMessages(next)
    setInput('')
    setThinking(true)
    try {
      const res = await fetch('/proxy/journal/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: next, system_prompt: systemPrompt }),
      })
      const data = await res.json() as { reply: string }
      if (data.reply) {
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
      }
    } finally {
      setThinking(false)
    }
  }

  async function handleSynthesize() {
    setState('synthesizing')
    setThinking(true)
    try {
      const res = await fetch('/proxy/journal/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, theme: sessionTheme, session_id: sessionId.current }),
      })
      const data = await res.json() as { entry: string }
      setEntry(data.entry ?? '')
      setState('done')
    } finally {
      setThinking(false)
    }
  }

  function handleReset() {
    setState('idle')
    setMessages([])
    setInput('')
    setEntry('')
    setSystemPrompt('')
    sessionId.current = `j-${Date.now()}`
  }

  const canSynthesize = messages.filter(m => m.role === 'user').length >= 3

  if (state === 'done') {
    return (
      <div style={{ display: 'grid', gap: 10 }}>
        <p style={chipStyle}>{sessionTheme} · saved</p>
        <p style={entryStyle}>{entry}</p>
        <button onClick={handleReset} style={secondaryBtnStyle}>new session</button>
      </div>
    )
  }

  if (state === 'idle') {
    return (
      <div style={{ display: 'grid', gap: 8 }}>
        <div style={themeRowStyle}>
          {THEMES.map(t => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              style={{ ...themeChipStyle, background: theme === t ? 'rgba(232,120,69,0.18)' : 'transparent', color: theme === t ? 'var(--orange-2)' : 'var(--text-muted)' }}
            >
              {t}
            </button>
          ))}
        </div>
        <button onClick={() => void handleStart()} disabled={thinking} style={{ ...startBtnStyle, opacity: thinking ? 0.5 : 1 }}>
          {thinking ? 'starting…' : 'start session'}
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div style={transcriptStyle}>
        {messages.map((m, i) => (
          <div key={i} style={m.role === 'assistant' ? kittyMsgStyle : jacobMsgStyle}>
            <span style={msgRoleStyle}>{m.role === 'assistant' ? 'kitty' : 'you'}</span>
            <p style={msgTextStyle}>{m.content}</p>
          </div>
        ))}
        {thinking && (
          <div style={kittyMsgStyle}>
            <span style={msgRoleStyle}>kitty</span>
            <p style={{ ...msgTextStyle, color: 'var(--text-faint)' }}>…</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: 'flex', gap: 5 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && void handleReply()}
          placeholder="reply…"
          disabled={thinking}
          style={{ ...replyInputStyle, opacity: thinking ? 0.5 : 1 }}
          autoFocus
        />
        <button onClick={() => void handleReply()} disabled={!input.trim() || thinking} style={{ ...sendBtnStyle, opacity: !input.trim() || thinking ? 0.4 : 1 }}>
          →
        </button>
      </div>

      <div style={{ display: 'flex', gap: 5 }}>
        {canSynthesize && (
          <button onClick={() => void handleSynthesize()} disabled={thinking} style={{ ...synthBtnStyle, flex: 1 }}>
            {state === 'synthesizing' ? 'writing…' : 'synthesize entry'}
          </button>
        )}
        <button onClick={handleReset} style={secondaryBtnStyle}>discard</button>
      </div>
    </div>
  )
}

const themeRowStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

const themeChipStyle: CSSProperties = {
  padding: '3px 8px',
  border: '1px solid var(--border-dim)',
  borderRadius: 12,
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  cursor: 'pointer',
  textTransform: 'lowercase',
}

const startBtnStyle: CSSProperties = {
  padding: '7px 12px',
  background: 'rgba(232,120,69,0.12)',
  border: '1px solid rgba(232,120,69,0.25)',
  borderRadius: 6,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--orange-2)',
  cursor: 'pointer',
  textAlign: 'left',
}

const transcriptStyle: CSSProperties = {
  maxHeight: 240,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: '4px 0',
}

const kittyMsgStyle: CSSProperties = {
  alignSelf: 'flex-start',
  maxWidth: '90%',
}

const jacobMsgStyle: CSSProperties = {
  alignSelf: 'flex-end',
  maxWidth: '90%',
  textAlign: 'right',
}

const msgRoleStyle: CSSProperties = {
  display: 'block',
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-faint)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  marginBottom: 2,
}

const msgTextStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  lineHeight: 1.55,
  color: 'var(--text-dim)',
  whiteSpace: 'pre-wrap',
}

const replyInputStyle: CSSProperties = {
  flex: 1,
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  padding: '5px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-dim)',
  outline: 'none',
  minWidth: 0,
}

const sendBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  flexShrink: 0,
}

const synthBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'rgba(78,201,176,0.1)',
  border: '1px solid rgba(78,201,176,0.25)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--teal)',
  cursor: 'pointer',
}

const secondaryBtnStyle: CSSProperties = {
  padding: '5px 10px',
  background: 'transparent',
  border: '1px solid var(--border-dim)',
  borderRadius: 5,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
  cursor: 'pointer',
}

const chipStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--teal)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
}

const entryStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  lineHeight: 1.7,
  color: 'var(--text-dim)',
  whiteSpace: 'pre-wrap',
  padding: '8px 10px',
  background: 'var(--recessed)',
  border: '1px solid var(--border-dim)',
  borderLeft: '3px solid var(--teal)',
  borderRadius: 5,
}
