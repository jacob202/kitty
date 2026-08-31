export type ContextReferenceKind = 'project' | 'artifact' | 'chat'

export interface ContextReference {
  kind: ContextReferenceKind
  id: string
  label: string
}

export interface ContextCandidate extends ContextReference {
  description?: string
}

export function appendContextMarkers(text: string, refs: ContextReference[]): string {
  if (refs.length === 0) return text
  const seen = new Set<string>()
  const markers = refs.flatMap((ref) => {
    const key = `${ref.kind}:${ref.id}`
    if (seen.has(key) || !ref.id.trim()) return []
    seen.add(key)
    return [`<!-- kitty-context:${ref.kind}:${ref.id.trim()} -->`]
  })
  if (markers.length === 0) return text
  return `${text.trimEnd()}\n\n${markers.join('\n')}`
}


const CONTEXT_MARKER_RE = /^\s*<!--\s*kitty-context:(?:project|artifact|chat):[^\s>]+\s*-->\s*$/gm

export function stripContextMarkers(text: string): string {
  return text.replace(CONTEXT_MARKER_RE, '').replace(/\n{3,}/g, '\n\n').trim()
}
