'use client'
import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { House, MessageSquare, CheckSquare, Terminal, Wrench, Plus, PanelLeft, type LucideIcon } from 'lucide-react'
import type { Chat } from '@/lib/types'

interface Props {
  chats: Chat[]
  onNewChat: () => void
  onSelectChat: (id: string) => void
  onViewChange: (view: string) => void
  onToggleSidebar: () => void
}

const VIEW_COMMANDS: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: 'home', label: 'home', icon: House },
  { id: 'chat', label: 'chat', icon: MessageSquare },
  { id: 'tasks', label: 'tasks', icon: CheckSquare },
  { id: 'tools', label: 'tools', icon: Wrench },
  { id: 'terminal', label: 'terminal', icon: Terminal },
]

export function CommandPalette({
  chats,
  onNewChat,
  onSelectChat,
  onViewChange,
  onToggleSidebar,
}: Props) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        // If the user is typing in an editable field (composer, search,
        // any contenteditable), don't steal the keystroke unless the
        // palette is already open (so Cmd+K can still close it).
        const target = e.target as HTMLElement | null
        const inEditable = !!target?.closest('input, textarea, [contenteditable="true"]')
        if (inEditable && !open) return
        e.preventDefault()
        setOpen(prev => !prev)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const close = () => setOpen(false)
  const fire = (fn: () => void) => () => {
    fn()
    close()
  }

  // Recent chats first — only those with content. Coerce updatedAt
  // defensively: hydrated-from-JSON chats can land here as strings.
  const recentChats = [...chats]
    .filter(c => c.messages.length > 0)
    .sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt))
    .slice(0, 8)

  if (!open) return null

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
        onClick={e => e.stopPropagation()}
        style={{
          width: 520,
          maxWidth: 'calc(100vw - 40px)',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          boxShadow: '4px 4px 0 var(--ink-deep)',
          overflow: 'hidden',
        }}
      >
        <Command label="Command palette" loop>
          <Command.Input
            autoFocus
            placeholder="Type a command or search…"
            style={{
              width: '100%',
              border: 'none',
              borderBottom: '1px solid var(--border)',
              background: 'transparent',
              padding: '14px 16px',
              fontFamily: 'var(--font-ui)',
              fontSize: 14,
              color: 'var(--text)',
              outline: 'none',
            }}
          />
          <Command.List style={{ maxHeight: 320, overflowY: 'auto', padding: 6 }}>
            <Command.Empty style={emptyStyle}>No results.</Command.Empty>

            <Command.Group heading="Actions" style={groupStyle}>
              <Item
                icon={Plus}
                label="New chat"
                shortcut="N"
                onSelect={fire(onNewChat)}
              />
              <Item
                icon={PanelLeft}
                label="Toggle sidebar"
                onSelect={fire(onToggleSidebar)}
              />
            </Command.Group>

            <Command.Group heading="Go to" style={groupStyle}>
              {VIEW_COMMANDS.map(v => (
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
                {recentChats.map(c => (
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

const groupStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  letterSpacing: '0.1em',
  color: 'var(--text-muted)',
  textTransform: 'lowercase',
}

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '8px 10px',
  fontFamily: 'var(--font-ui)',
  fontSize: 13,
  color: 'var(--text)',
  borderRadius: 4,
  cursor: 'pointer',
}

const emptyStyle: React.CSSProperties = {
  padding: '20px 10px',
  textAlign: 'center',
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-muted)',
}

const kbdStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '1px 5px',
  border: '1px solid var(--border)',
  borderRadius: 3,
  color: 'var(--text-muted)',
  background: 'var(--surface-mid)',
}
