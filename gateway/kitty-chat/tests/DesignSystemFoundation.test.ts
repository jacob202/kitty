import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8')

const semanticTokens = [
  '--color-canvas',
  '--color-surface',
  '--color-surface-elevated',
  '--color-separator',
  '--color-text-primary',
  '--color-text-secondary',
  '--color-text-muted',
  '--color-accent',
  '--color-success',
  '--color-warning',
  '--color-destructive',
  '--color-interactive-hover',
  '--color-selected',
  '--color-focus-ring',
  '--color-disabled',
]
describe('Kitty design foundations', () => {
  it('defines the semantic color contract', () => {
    for (const token of semanticTokens) {
      expect(css, `missing ${token}`).toContain(token)
    }
  })

  it('provides a visible keyboard focus treatment', () => {
    expect(css).toContain(':focus-visible')
    expect(css).toContain('var(--color-focus-ring)')
  })

  it('respects reduced motion beyond mascot animation', () => {
    expect(css).toMatch(/prefers-reduced-motion: reduce[\s\S]*transition-duration/)
  })

  it('does not use the legacy cosmic starfield treatment', () => {
    expect(css.toLowerCase()).not.toContain('starfield')
    expect(css).not.toContain('background-attachment: fixed')
  })
})

const layout = readFileSync(resolve(process.cwd(), 'src/app/layout.tsx'), 'utf8')

describe('Kitty browser chrome', () => {
  it('matches the canonical light canvas instead of the retired navy theme', () => {
    expect(layout).toContain('themeColor: "#F7F8FC"')
  })
})
