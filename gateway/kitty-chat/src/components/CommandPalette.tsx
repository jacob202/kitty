'use client'
import { useEffect, useState, Fragment } from 'react'
import { Command } from 'cmdk'
import { House, MessageSquare, CheckSquare, Terminal, Wrench, Plus, PanelLeft, Settings, GraduationCap, Image, Keyboard, Hammer, type LucideIcon } from 'lucide-react'
import type { Chat } from '@/lib/types'

interface Props {
  chats: Chat[]
  onNewChat: () => void
  onSelectChat: (id: string) => void
  onViewChange: (view: string) => void
  onToggleSidebar: () => void
  activeTaskCount?: number
}

const VIEW_COMMANDS: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: 'home', label: 'home', icon: House },
  { id: 'chat', label: 'chat', icon: MessageSquare },
  { id: 'settings', label: 'settings', icon: Settings },
  { id: 'tasks', label: 'tasks', icon: CheckSquare },
  { id: 'tools', label: 'tools', icon: Wrench },
  { id: 'terminal', label: 'terminal', icon: Terminal },
  { id: 'tutor', label: 'tutor', icon: GraduationCap },
  { id: 'images', label: 'image lab', icon: Image },
]

const SHORTCUTS: Array<{ key: string; description: string }> = [
  { key: '⌘K', description: 'open command palette' },
  { key: '⌘N', description: 'new chat' },
  { key: '⌘B', description: 'toggle sidebar' },
  { key: '⌘Enter', description: 'send message' },
  { key: '⌘⇧Enter', description: 'send with model override' },
  { key: 'Esc', description: 'stop generating / close palette' },
  { key: '⌘/', description: 'focus search in sidebar' },
  { key: '↑/↓', description: 'navigate palette / history' },
  { key: 'Tab', description: 'cycle model override (in composer)' },
]

const groupStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.1em',
  color: 'var(--ink-2)',
  textTransform: 'lowercase',
}

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '8px 10px',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  color: 'var(--ink)',
  borderRadius: 4,
  cursor: 'pointer',
}

const emptyStyle: React.CSSProperties = {
  padding: '20px 10px',
  textAlign: 'center',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--ink-2)',
}

const kbdStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '1px 5px',
  border: '1px solid var(--line)',
  borderRadius: 3,
  color: 'var(--ink-2)',
  background: 'var(--surface)',
}

function Item({
  icon: Icon,
  label,
  shortcut,
  onSelect,
}: {
  icon: LucideIcon
  label: string
  shortcut?: string
  onSelect: () => void
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      style={itemStyle}
      className="cmdk-item"
    >
      <Icon size={14} />
      <span style={{ flex: 1 }}>{label}</span>
      {shortcut && <kbd style={kbdStyle}>{shortcut}</kbd>}
    </Command.Item>
  )
}

function ShortcutsOverlay({ onClose, shortcuts }: { onClose: () => void; shortcuts: Array<{ key: string; description: string }> }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.6)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480,
          maxWidth: 'calc(100vw - 40px)',
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          borderRadius: 12,
          boxShadow: 'var(--shadow)',
          overflow: 'hidden',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--line)',
          background: 'var(--surface-2)',
        }}>
          <span style={{
            fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 18,
            letterSpacing: '-0.02em', color: 'var(--ink)',
          }}>keyboard shortcuts</span>
          <button
            onClick={onClose}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: 32, height: 32, border: 'none', borderRadius: 99,
              background: 'transparent', color: 'var(--ink-2)', cursor: 'pointer',
            }}
            aria-label="close"
          >
            <svg viewBox="0 0 24 24" style={{ width: 18, height: 18 }}><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth={2} strokeLinecap="round"/></svg>
          </button>
        </div>
        <div style={{ padding: '12px 20px 20px', maxHeight: '60vh', overflowY: 'auto' }}>
          <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '10px 16px', margin: 0 }}>
            {shortcuts.map((s, i) => (
              <Fragment key={i}>
                <dt style={{
                  fontFamily: 'var(--font-mono)', fontSize: 12,
                  fontWeight: 600, color: 'var(--ink)',
                  padding: '4px 8px', background: 'var(--surface-2)',
                  borderRadius: 6, textAlign: 'right',
                }}>{s.key}</dt>
                <dd style={{
                  margin: 0, fontSize: 13, color: 'var(--ink-2)',
                  paddingTop: 4,
                }}>{s.description}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      </div>
    </div>
  )
}

export function CommandPalette({
  chats,
  onNewChat,
  onSelectChat,
  onViewChange,
  onToggleSidebar,
  activeTaskCount = 0,
}: Props) {
  const [open, setOpen] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        const target = e.target as HTMLElement | null
        const inEditable = !!target?.closest('input, textarea, [contenteditable="true"]')
        if (inEditable && !open) return
        e.preventDefault()
        setOpen((prev) => !prev)
      } else if (e.key === 'Escape') {
        setOpen(false)
        setShowShortcuts(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const close = () => {
    setOpen(false)
    setShowShortcuts(false)
  }
  const fire = (fn: () => void) => () => {
    fn()
    close()
  }

  const recentChats = [...chats]
    .filter((c) => c.messages.length > 0)
    .sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt))
    .slice(0, 8)

  if (!open) return null

  if (showShortcuts) {
    return <ShortcutsOverlay onClose={close} shortcuts={SHORTCUTS} />
  }

  return (
    <div
      onClick={close}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.6)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 520,
          maxWidth: 'calc(100vw - 40px)',
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          borderRadius: 4,
          boxShadow: 'var(--shadow)',
          overflow: 'hidden',
        }}
      >
        <Command label="command palette" loop>
          <Command.Input
            autoFocus
            placeholder="type a command or search…"
            style={{
              width: '100%',
              border: 'none',
              borderBottom: '1px solid var(--line)',
              background: 'transparent',
              padding: '14px 16px',
              fontFamily: 'var(--font-body)',
              fontSize: 14,
              color: 'var(--ink)',
              outline: 'none',
            }}
          />
          <Command.List style={{ maxHeight: 320, overflowY: 'auto', padding: 6 }}>
            <Command.Empty style={emptyStyle}>no results.</Command.Empty>

            <Command.Group heading="Actions" style={groupStyle}>
              <Item
                icon={Plus}
                label="new chat"
                shortcut="N"
                onSelect={fire(onNewChat)}
              />
              <Item
                icon={PanelLeft}
                label="toggle sidebar"
                onSelect={fire(onToggleSidebar)}
              />
              <Item
                icon={Keyboard}
                label="keyboard shortcuts"
                shortcut="?"
                onSelect={() => setShowShortcuts(true)}
              />
            </Command.Group>

            <Command.Group heading="Builder" style={groupStyle}>
              <Item
                icon={CheckSquare}
                label={activeTaskCount > 0 ? `task queue (${activeTaskCount} active)` : 'task queue'}
                onSelect={fire(() => onViewChange('tasks'))}
              />
              <Item
                icon={Hammer}
                label="builder surface"
                onSelect={fire(() => onViewChange('builder'))}
              />
            </Command.Group>

            <Command.Group heading="Go to" style={groupStyle}>
              {VIEW_COMMANDS.map((v) => (
                <Item
                  key={v.id}
                  icon={v.icon}
                  label={v.label}
                  onSelect={fire(() => onViewChange(v.id))}
                />
              ))}
            </Command.Group>

            {recentChats.length > 0 && (
              <Command.Group heading="Recent chats" style={groupStyle}>
                {recentChats.map((c) => (
                  <Item
                    key={c.id}
                    icon={MessageSquare}
                    label={c.title}
                    onSelect={fire(() => onSelectChat(c.id))}
                  />
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}