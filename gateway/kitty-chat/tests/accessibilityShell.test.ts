import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const root = path.resolve(__dirname, '..')

describe('application accessibility shell', () => {
  it('provides a keyboard skip link to the existing main landmark', () => {
    const layout = fs.readFileSync(path.join(root, 'src/app/layout.tsx'), 'utf8')
    const page = fs.readFileSync(path.join(root, 'src/app/page.tsx'), 'utf8')

    expect(layout).toContain('href="#main-content"')
    expect(layout).toContain('Skip to main content')
    expect(page).toContain('id="main-content"')
  })

  it('gives keyboard focus a globally visible indicator', () => {
    const css = fs.readFileSync(path.join(root, 'src/app/globals.css'), 'utf8')

    expect(css).toContain('.skip-link:focus')
    expect(css).toContain('*:focus-visible')
  })
})
