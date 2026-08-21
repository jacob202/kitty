'use client'

import { useEffect, useState, type CSSProperties } from 'react'
import { Plus, Upload, User, X } from 'lucide-react'

type CharacterRef = {
  ref_id: string
  is_primary: boolean
  original_name: string | null
  storage_path: string
}

export type ImageCharacter = {
  character_id: string
  name: string
  description: string | null
  identity_preset: string
  references: CharacterRef[]
}

type Props = {
  selectedCharacterId: string | null
  onSelect: (characterId: string | null) => Promise<void> | void
}

async function jsonOrError(response: Response): Promise<any> {
  if (!response.ok) throw new Error(await response.text() || `request failed (${response.status})`)
  return response.json()
}
export function ImageCharacterTray({ selectedCharacterId, onSelect }: Props) {
  const [characters, setCharacters] = useState<ImageCharacter[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    try {
      const payload = await jsonOrError(await fetch('/proxy/studio/characters'))
      setCharacters(Array.isArray(payload.characters) ? payload.characters : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'could not load characters')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  async function createCharacter() {
    const trimmed = name.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError(null)
    try {
      const character = await jsonOrError(await fetch('/proxy/studio/characters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      })) as ImageCharacter

      if (file) {
        const form = new FormData()
        form.append('file', file)
        await jsonOrError(await fetch(`/proxy/studio/characters/${character.character_id}/references`, {
          method: 'POST',
          body: form,
        }))
      }

      await refresh()
      await onSelect(character.character_id)
      setName('')
      setFile(null)
      setCreating(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'could not create character')
    } finally {
      setBusy(false)
    }
  }

  const selected = characters.find(character => character.character_id === selectedCharacterId) ?? null

  return (
    <div style={trayStyle} data-testid="image-character-tray">
      <div style={rowStyle}>
        <div style={labelStyle}><User size={13} /> character</div>
        <select
          aria-label="character"
          value={selectedCharacterId ?? ''}
          disabled={loading || busy}
          onChange={event => void onSelect(event.target.value || null)}
          style={selectStyle}
        >
          <option value="">none</option>
          {characters.map(character => (
            <option key={character.character_id} value={character.character_id}>{character.name}</option>
          ))}
        </select>
        {selected && <span style={metaStyle}>{selected.references?.length ?? 0} refs</span>}
        <button type="button" onClick={() => setCreating(value => !value)} style={buttonStyle}>
          {creating ? <X size={12} /> : <Plus size={12} />}
          {creating ? 'close' : 'new'}
        </button>
      </div>

      {creating && (
        <div style={createStyle}>
          <input
            aria-label="new character name"
            value={name}
            onChange={event => setName(event.target.value)}
            placeholder="character name"
            style={inputStyle}
          />
          <label style={uploadStyle}>
            <Upload size={12} />
            {file ? file.name : 'reference'}
            <input type="file" accept="image/*" onChange={event => setFile(event.target.files?.[0] ?? null)} style={{ display: 'none' }} />
          </label>
          <button type="button" disabled={!name.trim() || busy} onClick={() => void createCharacter()} style={buttonStyle}>
            {busy ? 'saving…' : 'create'}
          </button>
        </div>
      )}

      {error && <div role="alert" style={errorStyle}>{error}</div>}
    </div>
  )
}

const trayStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8, padding: 10, border: '1px solid var(--line)', borderRadius: 12, background: 'var(--surface)' }
const rowStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }
const labelStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-2)' }
const selectStyle: CSSProperties = { minWidth: 150, border: '1px solid var(--line)', borderRadius: 8, padding: '5px 7px', background: 'var(--bg)', color: 'var(--ink)', fontFamily: 'var(--font-mono)', fontSize: 10 }
const metaStyle: CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--ink-2)' }
const buttonStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 4, border: '1px solid var(--line)', borderRadius: 7, padding: '5px 8px', background: 'transparent', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 9, cursor: 'pointer' }
const createStyle: CSSProperties = { display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }
const inputStyle: CSSProperties = { flex: 1, minWidth: 150, border: '1px solid var(--line)', borderRadius: 8, padding: '6px 8px', background: 'var(--bg)', color: 'var(--ink)', fontSize: 12 }
const uploadStyle: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer', border: '1px dashed var(--line)', borderRadius: 8, padding: '5px 8px', color: 'var(--ink-2)', fontSize: 10 }
const errorStyle: CSSProperties = { color: 'var(--c-red)', fontSize: 11 }
