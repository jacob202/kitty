'use client'
import type { CSSProperties } from 'react'
import { Home, MessageCircle, Sparkles, BookOpen, Brain, Wrench, Settings } from 'lucide-react'
import type { KittyView } from '@/hooks/useViewRouter'

const TABS: { view: KittyView; icon: typeof Home; label: string }[] = [
  { view: 'home',   icon: Home,             label: 'home' },
  { view: 'chat',   icon: MessageCircle,    label: 'chat' },
  { view: 'tools',  icon: Sparkles,         label: 'create' },
  { view: 'tutor',  icon: BookOpen,         label: 'learn' },
  { view: 'builder',icon: Wrench,           label: 'work' },
]

interface Props {
  activeView: KittyView
  onNavigate: (view: KittyView) => void
}

export function BottomNav({ activeView, onNavigate }: Props) {
  return (
    <nav
      aria-label="Main navigation"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 90,
        background: 'var(--surface)',
        borderTop: '1px solid var(--line)',
        display: 'flex',
        justifyContent: 'space-around',
        alignItems: 'center',
        padding: '6px 0 env(safe-area-inset-bottom, 8px)',
        minHeight: 56,
      }}
    >
      {TABS.map(({ view, icon: Icon, label }) => {
        const active = activeView === view
        return (
          <button
            key={view}
            onClick={() => onNavigate(view)}
            aria-label={label}
            aria-current={active ? 'page' : undefined}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: active ? 'var(--cat-ginger)' : 'var(--ink-2)',
              padding: '6px 12px',
              minWidth: 56,
              minHeight: 44,
              borderRadius: 10,
              fontFamily: 'var(--font-body)',
              fontSize: 10,
              fontWeight: active ? 600 : 400,
              transition: 'color 0.15s ease',
            }}
          >
            <Icon size={20} />
            <span>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}

const MOBILE_BOTTOM_NAV_HEIGHT = 72
export const MOBILE_BOTTOM_PADDING = `${MOBILE_BOTTOM_NAV_HEIGHT + 16}px`
