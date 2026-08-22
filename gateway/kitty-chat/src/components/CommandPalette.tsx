'use client'
import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { House, MessageSquare, CheckSquare, Plus, PanelLeft, Settings, Image, BookOpen, Users, type LucideIcon } from 'lucide-react'
import { fetchGatewaySearch, type GatewaySearchHit } from '@/lib/gateway'
import type { Chat } from '@/lib/types'

interface Props {
  chats: Chat[]
  onNewChat: () => void
  onSelectChat: (id: string) => void
  onViewChange: (view: string) => void
  onToggleSidebar: () => void
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

const VIEW_COMMANDS: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: 'home', label: 'home', icon: House },
  { id: 'chat', label: 'chat', icon: MessageSquare },
  { id: 'work', label: 'work', icon: CheckSquare },
  { id: 'projects', label: 'projects', icon: BookOpen },
  { id: 'studio', label: 'studio', icon: Image },
  { id: 'agents', label: 'agents', icon: Users },
  { id: 'library', label: 'library', icon: BookOpen },
  { id: 'tutor', label: 'tutor', icon: BookOpen },
  { id: 'journal', label: 'journal', icon: BookOpen },
  { id: 'settings', label: 'settings', icon: Settings },
]

export function CommandPalette({
  chats,
  onNewChat,
  onSelectChat,
  onViewChange,
  onToggleSidebar,
  open: externalOpen,
  onOpenChange,
}: Props) {
  const [internalOpen, setInternalOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [searchHits, setSearchHits] = useState<GatewaySearchHit[]>([])
  const [degradedStores, setDegradedStores] = useState<string[]>([])
  const [degradedErrors, setDegradedErrors] = useState<string[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const open = externalOpen ?? internalOpen
  const setOpen = onOpenChange ?? setInternalOpen

  const clearSearch = () => {
    setSearchHits([])
    setDegradedStores([])
    setDegradedErrors([])
    setSearchError(null)
    setSearching(false)
  }
  const close = () => {
    setQuery('')
    clearSearch()
    setOpen(false)
  }
  const changeQuery = (value: string) => {
    clearSearch()
    setSearching(open && value.trim().length >= 2)
    setQuery(value)
  }

  useEffect(() => {
    const q = query.trim()
    if (!open || q.length < 2) {
      clearSearch()
      return
    }
    setSearching(true)
    const controller = new AbortController()
    const timeoutId = window.setTimeout(async () => {
      const payload = await fetchGatewaySearch(q, 5, controller.signal)
      if (!controller.signal.aborted) {
        setSearchHits(payload.hits)
        setDegradedStores(payload.degradedStores ?? [])
        setDegradedErrors(payload.degradedErrors ?? [])
        setSearchError(payload.error)
        setSearching(false)
      }
    }, 250)
    return () => {
      window.clearTimeout(timeoutId)
      controller.abort()
    }
  }, [open, query])

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
        if (open) close()
        else setOpen(true)
      } else if (e.key === 'Escape') {
        close()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

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
          border: '1px solid var(--line)',
          borderRadius: 4,
          boxShadow: 'var(--shadow)',
          overflow: 'hidden',
        }}
      >
        <Command label="command palette" loop>
          <Command.Input
            autoFocus
            value={query}
            onValueChange={changeQuery}
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
            <Command.Empty style={emptyStyle}>
              {searching ? 'searching Kitty…' : 'no results.'}
            </Command.Empty>

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


            {searchHits.length > 0 && (
              <Command.Group heading="Kitty search" style={groupStyle}>
                {searchHits.map((hit, index) => {
                  const targetView = searchViewForHit(hit)
                  return (
                    <Command.Item
                      key={`${hit.kind ?? 'search'}-${hit.source}-${index}`}
                      value={`${query} ${hit.title} ${hit.text} ${hit.source}`}
                      disabled={!targetView}
                      onSelect={targetView ? fire(() => onViewChange(targetView)) : undefined}
                      style={itemStyle}
                      className="cmdk-item"
                    >
                      <BookOpen size={14} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block' }}>{hit.title}</span>
                        <span style={{ display: 'block', color: 'var(--ink-2)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {hit.text}
                        </span>
                      </span>
                      {!targetView && <span style={{ fontSize: 10, color: 'var(--ink-2)' }}>preview only</span>}
                    </Command.Item>
                  )
                })}
              </Command.Group>
            )}

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
          {(degradedStores.length > 0 || degradedErrors.length > 0) && (
            <div
              role="status"
              style={{ padding: '8px 12px', borderTop: '1px solid var(--line)', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}
            >
              {degradedStores.length > 0
                ? `some sources unavailable: ${degradedStores.join(', ')}`
                : 'some search sources are unavailable'}
              {degradedErrors.length > 0 && (
                <details>
                  <summary>technical details</summary>
                  {degradedErrors.map((error, index) => <div key={`${error}-${index}`}>{error}</div>)}
                </details>
              )}
            </div>
          )}
          {searchError && (
            <div
              role="alert"
              style={{ padding: '8px 12px', borderTop: '1px solid var(--line)', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }}
            >
              search unavailable — check that Kitty is running, then try again.
              <details>
                <summary>technical details</summary>
                <div>{searchError}</div>
              </details>
            </div>
          )}
        </Command>
      </div>
    </div>
  )
}

function searchViewForHit(hit: GatewaySearchHit): string | null {
  if (hit.kind === 'knowledge') return 'library'
  return null
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
