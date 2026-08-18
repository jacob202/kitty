import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const page = fs.readFileSync(path.resolve(__dirname, '../src/app/page.tsx'), 'utf8')

function between(start: string, end: string): string {
  const from = page.indexOf(start)
  const to = page.indexOf(end, from + start.length)
  expect(from).toBeGreaterThanOrEqual(0)
  expect(to).toBeGreaterThan(from)
  return page.slice(from, to)
}

describe('product surface shell ownership', () => {
  it('does not mount chat history beside Home on desktop', () => {
    const sidebar = between('{!k.isMobile &&', '<KittyRuntimeProvider')
    expect(sidebar).toContain("k.activeView === 'chat'")
    expect(sidebar).not.toContain("k.activeView === 'chat' || k.activeView === 'home'")
  })

  it('does not mount the chat composer under Home', () => {
    const composer = between('<InputBar', '</main>')
    const conditionWindow = page.slice(Math.max(0, page.indexOf('<InputBar') - 180), page.indexOf('<InputBar'))
    expect(conditionWindow).toContain("k.activeView === 'chat'")
    expect(conditionWindow).not.toContain("k.activeView === 'chat' || k.activeView === 'home'")
    expect(composer).toContain('onSend={k.handleSend}')
  })

  it('keeps the fixed mascot off Home where the dashboard has an inline mascot', () => {
    expect(page).toContain("k.activeView !== 'home' && <CatCorner")
  })
})
