'use client'

import { createContext, useContext, useState } from 'react'

import { useKitty } from '@/state/KittyContext'
import { useGatewayWeather } from '@/lib/queries'
import { useGatewayCalendarToday, useGatewayCalendarUpcoming } from '@/lib/dashboard-calendar'

import ProjectsView from './ProjectsView'
import { TodoPanel } from './TodoPanel'
import { JournalPanel } from './JournalPanel'

// Warm-paper palette — Jacob's "Anthropic-ish: green, orange, brown, cream"
// direction from the Claude Design mockups (Palette A/B there). Two variants,
// not one fixed look: day/cosmic gets the light "warm paper" card, night gets
// its "dark ink" twin, so the app's theme toggle still does something here
// instead of this view silently ignoring it.
const WP_DAY = {
  cream: '#F2EBDE',
  creamSoft: '#EBE1CE',
  ink: '#241D17',
  inkDim: '#6B5F52',
  inkFaint: '#8B7F70',
  brown: '#3A2F26',
  orange: '#C1602E',
  green: '#7C9070',
  line: '#D9CDB6',
  danger: '#B4483A',
}

const WP_NIGHT = {
  cream: '#241D17',
  creamSoft: '#1B1611',
  ink: '#F2EBDE',
  inkDim: '#C9BDA9',
  inkFaint: '#9C8F7D',
  brown: '#332A22',
  orange: '#E88A4C',
  green: '#8FB08A',
  line: '#4A4038',
  danger: '#E88A78',
}

type Palette = typeof WP_DAY

const PaletteContext = createContext<Palette>(WP_DAY)
const usePalette = () => useContext(PaletteContext)

const TABS = [
  { id: 'overview', label: 'overview' },
  { id: 'projects', label: 'projects' },
  { id: 'tasks', label: 'tasks' },
  { id: 'notes', label: 'notes' },
  { id: 'calendar', label: 'calendar' },
  { id: 'assistant', label: 'assistant' },
] as const

type TabId = (typeof TABS)[number]['id']

const serif: React.CSSProperties = { fontFamily: 'Georgia, "Source Serif 4", serif' }
const mono: React.CSSProperties = { fontFamily: 'ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, monospace' }

function Tile({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  const WP = usePalette()
  return (
    <div
      style={{
        background: WP.cream,
        border: `1px solid ${WP.line}`,
        borderRadius: 10,
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        minHeight: 96,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function TileLabel({ children, tone }: { children: React.ReactNode; tone?: 'danger' }) {
  const WP = usePalette()
  return (
    <div
      style={{
        ...mono,
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: tone === 'danger' ? WP.danger : WP.inkFaint,
      }}
    >
      {children}
    </div>
  )
}

function WeatherTile() {
  const WP = usePalette()
  const weather = useGatewayWeather()
  const w = weather.data?.weather
  const err = weather.data?.error
  return (
    <Tile>
      <TileLabel>weather</TileLabel>
      {w && w.temp_c != null ? (
        <>
          <div style={{ ...serif, fontSize: 30, color: WP.ink, lineHeight: 1 }}>{Math.round(w.temp_c)}°c</div>
          <div style={{ ...mono, fontSize: 12, color: WP.inkDim }}>
            {w.description || 'clear'}
            {w.feels_like_c != null ? ` · feels like ${Math.round(w.feels_like_c)}°` : ''}
          </div>
        </>
      ) : (
        <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>
          {weather.isLoading ? 'checking…' : err || 'weather not connected'}
        </div>
      )}
    </Tile>
  )
}

function CalendarTodayTile() {
  const WP = usePalette()
  const today = useGatewayCalendarToday()
  const cal = today.data?.calendar
  const err = today.data?.error
  if (today.isLoading) {
    return (
      <Tile>
        <TileLabel>today's schedule</TileLabel>
        <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>checking…</div>
      </Tile>
    )
  }
  if (!cal?.available) {
    return (
      <Tile>
        <TileLabel tone={err ? 'danger' : undefined}>today's schedule</TileLabel>
        <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>
          {err || 'calendar not connected on this mac'}
        </div>
      </Tile>
    )
  }
  return (
    <Tile style={{ gridColumn: '1 / -1' }}>
      <TileLabel>today's schedule</TileLabel>
      {cal.events.length === 0 ? (
        <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>nothing on the calendar today</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {cal.events.map((ev, i) => (
            <div
              key={i}
              style={{
                display: 'grid',
                gridTemplateColumns: '72px 1fr',
                gap: 12,
                padding: '7px 0',
                borderTop: i === 0 ? 'none' : `1px solid ${WP.line}`,
                fontSize: 12.5,
              }}
            >
              <span style={{ ...mono, color: WP.inkFaint }}>{ev.start_time || ev.start || ''}</span>
              <span style={{ color: WP.ink }}>{ev.title || 'untitled event'}</span>
            </div>
          ))}
        </div>
      )}
    </Tile>
  )
}

function ProjectsTile({ projects, onNavigate }: { projects: any[]; onNavigate?: (v: string) => void }) {
  const WP = usePalette()
  // Match Home's "active projects" count (HomeState.tsx ActiveProjects) so the
  // same number doesn't read differently depending which screen shows it.
  const active = projects.filter((p) => p.status === 'active')
  return (
    <Tile>
      <TileLabel>active projects</TileLabel>
      <div style={{ ...serif, fontSize: 30, color: WP.ink, lineHeight: 1 }}>{active.length}</div>
      <div style={{ ...mono, fontSize: 12, color: WP.inkDim }}>
        {active.length === 0 ? 'none yet' : active.slice(0, 3).map((p) => p.name).filter(Boolean).join(' · ')}
      </div>
      <button
        onClick={() => onNavigate?.('projects')}
        style={{
          ...mono, marginTop: 'auto', alignSelf: 'flex-start', background: 'transparent',
          border: 'none', color: WP.orange, fontSize: 12, fontWeight: 700, cursor: 'pointer', padding: 0,
        }}
      >
        open projects →
      </button>
    </Tile>
  )
}

function TabStrip({ active, onSelect }: { active: TabId; onSelect: (t: TabId) => void }) {
  const WP = usePalette()
  return (
    <div style={{ display: 'flex', gap: 4, padding: '0 4px', overflowX: 'auto' }}>
      {TABS.map((t) => {
        const isActive = t.id === active
        return (
          <button
            key={t.id}
            onClick={() => onSelect(t.id)}
            style={{
              ...mono,
              fontSize: 12.5,
              padding: '9px 16px',
              border: 'none',
              borderBottom: isActive ? `2px solid ${WP.orange}` : '2px solid transparent',
              background: 'transparent',
              color: isActive ? WP.ink : WP.inkFaint,
              fontWeight: isActive ? 700 : 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}

function CalendarTab() {
  const WP = usePalette()
  const upcoming = useGatewayCalendarUpcoming(14)
  const cal = upcoming.data?.calendar
  const err = upcoming.data?.error
  return (
    <div style={{ padding: '4px 4px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <CalendarTodayTile />
      <Tile>
        <TileLabel tone={!upcoming.isLoading && !cal?.available && err ? 'danger' : undefined}>
          next 14 days
        </TileLabel>
        {upcoming.isLoading ? (
          <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>checking…</div>
        ) : !cal?.available ? (
          <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>
            {err || 'calendar not connected on this mac'}
          </div>
        ) : cal.events.length === 0 ? (
          <div style={{ ...mono, fontSize: 12, color: WP.inkFaint }}>nothing coming up</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {cal.events.map((ev, i) => (
              <div
                key={i}
                style={{
                  display: 'grid', gridTemplateColumns: '140px 1fr', gap: 12, padding: '7px 0',
                  borderTop: i === 0 ? 'none' : `1px solid ${WP.line}`, fontSize: 12.5,
                }}
              >
                <span style={{ ...mono, color: WP.inkFaint }}>
                  {ev.start_date && ev.start_time ? `${ev.start_date} ${ev.start_time}` : ev.start || ''}
                </span>
                <span style={{ color: WP.ink }}>{ev.title || 'untitled event'}</span>
              </div>
            ))}
          </div>
        )}
      </Tile>
    </div>
  )
}

function AssistantTab({ onNavigate }: { onNavigate?: (v: string) => void }) {
  const WP = usePalette()
  return (
    <div style={{ padding: '24px 4px', display: 'flex', justifyContent: 'center' }}>
      <Tile style={{ maxWidth: 420, alignItems: 'center', textAlign: 'center', gap: 12, padding: '28px 24px' }}>
        <div style={{ ...serif, fontSize: 22, color: WP.ink }}>ask kitty anything</div>
        <div style={{ ...mono, fontSize: 12, color: WP.inkDim }}>
          the assistant tab hands off to the real chat — full history, tools, and memory live there.
        </div>
        <button
          onClick={() => onNavigate?.('chat')}
          style={{
            ...mono, marginTop: 4, background: WP.orange, color: WP.cream, border: 'none',
            padding: '10px 20px', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer',
          }}
        >
          open chat →
        </button>
      </Tile>
    </div>
  )
}

// Neutral pose from the mascot set: cream line art with no background, so it
// sits on the dark WP.ink card below. The "barbie"/"princess" costume poses
// use pink accents that clash with this palette; other neutral poses would
// work here too if this one ever needs swapping.
function MascotTile() {
  const WP = usePalette()
  return (
    <Tile>
      <TileLabel>mascot</TileLabel>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ background: WP.ink, borderRadius: 10, padding: 10, flex: 'none' }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/mascots/kitty-warm-paper.svg" alt="kitty" style={{ width: 40, height: 40, display: 'block' }} />
        </div>
      </div>
    </Tile>
  )
}

function DashboardBody({
  isMobile,
  onNavigate,
  projects,
}: {
  isMobile: boolean
  onNavigate: (v: string) => void
  projects: any[]
}) {
  const WP = usePalette()
  const [tab, setTab] = useState<TabId>('overview')

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        background: WP.creamSoft,
        color: WP.ink,
      }}
    >
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: isMobile ? '14px 14px 6px' : '20px 24px 6px',
        }}
      >
        <div style={{ ...serif, fontSize: isMobile ? 20 : 26, color: WP.ink }}>dashboard</div>
        <div style={{ ...mono, fontSize: 11, color: WP.inkFaint }}>kitty / {tab}</div>
      </div>

      <TabStrip active={tab} onSelect={setTab} />
      <div style={{ height: 1, background: WP.line, margin: '0 4px' }} />

      <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '12px 14px 100px' : '16px 24px 40px' }}>
        {tab === 'overview' && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)',
              gap: 10,
            }}
          >
            <WeatherTile />
            <ProjectsTile projects={projects} onNavigate={onNavigate} />
            <MascotTile />
            <CalendarTodayTile />
          </div>
        )}
        {tab === 'projects' && <ProjectsView isMobile={isMobile} />}
        {tab === 'tasks' && <TodoPanel />}
        {tab === 'notes' && <JournalPanel />}
        {tab === 'calendar' && <CalendarTab />}
        {tab === 'assistant' && <AssistantTab onNavigate={onNavigate} />}
      </div>
    </div>
  )
}

export default function DashboardView({
  isMobile: isMobileProp,
  onNavigate,
}: {
  isMobile?: boolean
  onNavigate?: (view: string) => void
}) {
  const k = useKitty()
  const isMobile = isMobileProp ?? k.isMobile
  const navigate = onNavigate ?? k.setActiveView
  const projects: any[] = k.projects ?? []
  const palette = k.theme === 'night' ? WP_NIGHT : WP_DAY

  return (
    <PaletteContext.Provider value={palette}>
      <DashboardBody isMobile={isMobile} onNavigate={navigate} projects={projects} />
    </PaletteContext.Provider>
  )
}
