import { describe, expect, it } from 'vitest'
import { appendContextMarkers, stripContextMarkers } from '../src/lib/context-references'

describe('context reference persistence', () => {
  it('keeps the visible prompt readable and appends durable hidden ids', () => {
    const value = appendContextMarkers('Compare @kitty with @research-report.md', [
      { kind: 'project', id: '7', label: 'kitty' },
      { kind: 'artifact', id: 'artifact_1', label: 'research-report.md' },
    ])

    expect(value).toBe(
      'Compare @kitty with @research-report.md\n\n' +
      '<!-- kitty-context:project:7 -->\n' +
      '<!-- kitty-context:artifact:artifact_1 -->',
    )
  })

  it('removes durable markers from model/search-visible text', () => {
    expect(stripContextMarkers(
      'Compare @kitty\n\n<!-- kitty-context:project:7 -->\n<!-- kitty-context:chat:chat-9 -->',
    )).toBe('Compare @kitty')
  })
})
