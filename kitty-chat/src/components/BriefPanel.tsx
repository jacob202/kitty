'use client'
import { useState, useEffect } from 'react'
import { Chat } from '@/lib/types'

// ── Data fetching ─────────────────────────────────────────────

interface HNStory { id: number; title: string; url?: string; score: number; by: string }

async function fetchHNStories(n = 4): Promise<HNStory[]> {
  const ids: number[] = await fetch(
    'https://hacker-news.firebaseio.com/v0/topstories.json'
  ).then(r => r.json())
  return Promise.all(
    ids.slice(0, n).map(id =>
      fetch(`https://hacker-news.firebaseio.com/v0/item/${id}.json`).then(r => r.json())
    )
  )
}

interface Weather {
  temp: number
  unit: string
  desc: string
  icon: string
  city: string
  wind: number
  humidity: number
}

// WMO weather code → emoji + label
const WMO: Record<number, [string, string]> = {
  0: ['☀️', 'Clear'],
  1: ['🌤', 'Mostly clear'], 2: ['⛅', 'Partly cloudy'], 3: ['☁️', 'Overcast'],
  45: ['🌫', 'Foggy'], 48: ['🌫', 'Icy fog'],
  51: ['🌦', 'Light drizzle'], 53: ['🌦', 'Drizzle'], 55: ['🌧', 'Heavy drizzle'],
  61: ['🌧', 'Light rain'], 63: ['🌧', 'Rain'], 65: ['🌧', 'Heavy rain'],
  71: ['🌨', 'Light snow'], 73: ['🌨', 'Snow'], 75: ['❄️', 'Heavy snow'],
  80: ['🌦', 'Showers'], 81: ['🌧', 'Rain showers'], 82: ['⛈', 'Violent showers'],
  95: ['⛈', 'Thunderstorm'], 96: ['⛈', 'Hail storm'], 99: ['⛈', 'Hail storm'],
}

async function fetchWeather(): Promise<Weather> {
  // get lat/lon from IP
  const geo = await fetch('https://ipapi.co/json/').then(r => r.json())
  const { latitude, longitude, city } = geo

  const wx = await fetch(
    `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}` +
    `&current_weather=true&hourly=relativehumidity_2m&timezone=auto&forecast_days=1`
  ).then(r => r.json())

  const { temperature, windspeed, weathercode } = wx.current_weather
  const humidity = wx.hourly?.relativehumidity_2m?.[new Date().getHours()] ?? 0
  const [icon, desc] = WMO[weathercode] ?? ['🌡', 'Unknown']

  return {
    temp: Math.round(temperature),
    unit: '°C',
    desc,
    icon,
    city: city ?? 'Local',
    wind: Math.round(windspeed),
    humidity,
  }
}

// ── Helpers ───────────────────────────────────────────────────

function greeting() {
  const h = new Date().getHours()
  if (h < 5)  return 'still up?'
  if (h < 12) return 'good morning'
  if (h < 17) return 'good afternoon'
  if (h < 21) return 'good evening'
  return 'late night'
}

const PROMPTS = [
  { icon: '⚡', label: 'Debug an error',    text: 'Help me debug this error:\n' },
  { icon: '✦',  label: 'Explain code',      text: 'Explain what this code does:\n' },
  { icon: '✍',  label: 'Write a function',  text: 'Write a function that ' },
  { icon: '⟳',  label: 'Refactor',          text: 'Refactor this to be cleaner:\n' },
  { icon: '◈',  label: 'Brainstorm',        text: 'Brainstorm ideas for ' },
  { icon: '▣',  label: 'Summarize',         text: 'Summarize the following:\n' },
]

// ── Component ─────────────────────────────────────────────────

interface Props {
  chats: Chat[]
  onSelectChat: (id: string) => void
  onPrompt: (text: string) => void
}

export function BriefPanel({ chats, onSelectChat, onPrompt }: Props) {
  const [stories, setStories] = useState<HNStory[]>([])
  const [weather, setWeather] = useState<Weather | null>(null)

  useEffect(() => {
    fetchHNStories(4).then(setStories).catch(() => {})
    fetchWeather().then(setWeather).catch(() => {})
  }, [])

  const recentChats = [...chats]
    .filter(c => c.messages.length > 0)
    .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
    .slice(0, 4)

  const lastChat = recentChats[0]
  const lastAiMsg = lastChat?.messages.filter(m => m.role === 'assistant').at(-1)

  return (
    <div style={{
      flex: 1, overflowY: 'auto',
      padding: '28px 36px 24px',
      display: 'flex', flexDirection: 'column', gap: 22,
    }}>

      {/* ── Header row: greeting + weather ── */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-ui)', fontSize: 34, fontWeight: 700,
            color: 'var(--text)', letterSpacing: '0.5px', lineHeight: 1,
          }}>
            {greeting()}<span style={{ color: 'var(--orange)' }}>.</span>
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 12,
            color: 'var(--text-muted)', marginTop: 7,
          }}>
            {new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
        </div>

        {/* Weather pill */}
        {weather ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 14,
            background: 'var(--bg-card)', borderRadius: 12,
            padding: '12px 20px',
          }}>
            <span style={{ fontSize: 32, lineHeight: 1 }}>{weather.icon}</span>
            <div>
              <div style={{
                fontFamily: 'var(--font-ui)', fontSize: 28, fontWeight: 700,
                color: 'var(--text)', lineHeight: 1,
              }}>
                {weather.temp}{weather.unit}
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 11,
                color: 'var(--text-muted)', marginTop: 3,
              }}>
                {weather.desc} · {weather.city}
              </div>
            </div>
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 3,
              borderLeft: '1px solid #222', paddingLeft: 14,
            }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                💨 {weather.wind} km/h
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                💧 {weather.humidity}%
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-faint)',
            background: 'var(--bg-card)', borderRadius: 10, padding: '10px 16px',
          }}>
            loading weather…
          </div>
        )}
      </div>

      {/* ── Two-col: last chat + news ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 16 }}>

        {/* Last session */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Label>last session</Label>
          {lastChat ? (
            <Tile onClick={() => onSelectChat(lastChat.id)} hoverable>
              <div style={{
                fontFamily: 'var(--font-ui)', fontSize: 16, fontWeight: 700,
                color: 'var(--text)', letterSpacing: '0.3px', marginBottom: 8,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {lastChat.title}
              </div>
              {lastAiMsg && (
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 12,
                  color: 'var(--text-muted)', lineHeight: 1.7,
                  display: '-webkit-box', WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}>
                  {lastAiMsg.content.replace(/```[\s\S]*?```/g, '[code]').slice(0, 200)}
                </div>
              )}
              <div style={{
                marginTop: 12, fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 700,
                color: 'var(--orange)', letterSpacing: '0.5px',
              }}>
                continue →
              </div>
            </Tile>
          ) : (
            <Tile>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>
                no chats yet
              </div>
            </Tile>
          )}

          {/* Recent */}
          {recentChats.length > 1 && (
            <>
              <Label style={{ marginTop: 6 }}>recent</Label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {recentChats.slice(1).map(c => (
                  <button key={c.id} onClick={() => onSelectChat(c.id)} style={{
                    textAlign: 'left', background: 'none', border: 'none',
                    padding: '8px 10px', borderRadius: 7, cursor: 'pointer',
                    fontFamily: 'var(--font-mono)', fontSize: 12,
                    color: 'var(--text-muted)',
                    display: 'flex', alignItems: 'center', gap: 8,
                    transition: 'color 0.1s, background 0.1s',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.background = '#1a1a1a' }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'none' }}
                  >
                    <span style={{ color: 'var(--purple)', opacity: 0.5 }}>›</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                      {c.title}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Top stories */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Label>
            top stories
            <span style={{ marginLeft: 6, fontWeight: 400, color: 'var(--text-faint)' }}>via hacker news</span>
          </Label>
          <Tile style={{ padding: '4px 0' }}>
            {stories.length === 0 ? (
              <div style={{ padding: '14px 16px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>
                loading…
              </div>
            ) : stories.map((s, i) => (
              <a key={s.id}
                href={s.url ?? `https://news.ycombinator.com/item?id=${s.id}`}
                target="_blank" rel="noopener noreferrer"
                style={{
                  display: 'flex', gap: 12, alignItems: 'flex-start',
                  padding: '11px 16px', textDecoration: 'none',
                  borderBottom: i < stories.length - 1 ? '1px solid #191919' : 'none',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => (e.currentTarget as HTMLAnchorElement).style.background = '#181818'}
                onMouseLeave={e => (e.currentTarget as HTMLAnchorElement).style.background = 'transparent'}
              >
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11,
                  color: 'var(--orange)', opacity: 0.5, flexShrink: 0, paddingTop: 2,
                }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 13,
                    color: 'var(--text-dim)', lineHeight: 1.5,
                    display: '-webkit-box', WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical', overflow: 'hidden',
                  }}>
                    {s.title}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
                    {s.score} pts · {s.by}
                  </div>
                </div>
              </a>
            ))}
          </Tile>
        </div>
      </div>

      {/* ── Prompt grid ── */}
      <div>
        <Label>ask kitty</Label>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 10, marginTop: 10,
        }}>
          {PROMPTS.map(p => (
            <button key={p.label} onClick={() => onPrompt(p.text)} style={{
              textAlign: 'left', cursor: 'pointer',
              background: 'var(--bg-card)',
              border: 'none', borderRadius: 10,
              padding: '14px 16px',
              fontFamily: 'var(--font-ui)',
              transition: 'background 0.15s, box-shadow 0.15s',
            }}
              onMouseEnter={e => {
                e.currentTarget.style.background = '#1a1527'
                e.currentTarget.style.boxShadow = '0 0 0 1px var(--purple-glow)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'var(--bg-card)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <div style={{ fontSize: 20, marginBottom: 7, lineHeight: 1 }}>{p.icon}</div>
              <div style={{
                fontSize: 15, fontWeight: 700, color: 'var(--text)',
                letterSpacing: '0.2px', lineHeight: 1,
              }}>
                {p.label}
              </div>
            </button>
          ))}
        </div>
      </div>

    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────

function Label({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
      color: 'var(--text-faint)', letterSpacing: '1.5px', textTransform: 'uppercase',
      ...style,
    }}>
      {children}
    </div>
  )
}

function Tile({
  children, onClick, hoverable, style,
}: {
  children: React.ReactNode
  onClick?: () => void
  hoverable?: boolean
  style?: React.CSSProperties
}) {
  return (
    <div onClick={onClick} style={{
      background: 'var(--bg-card)',
      borderRadius: 10, padding: '16px',
      cursor: hoverable ? 'pointer' : 'default',
      transition: 'background 0.15s',
      ...style,
    }}
      onMouseEnter={e => { if (hoverable) (e.currentTarget as HTMLDivElement).style.background = '#1e1e1e' }}
      onMouseLeave={e => { if (hoverable) (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-card)' }}
    >
      {children}
    </div>
  )
}
