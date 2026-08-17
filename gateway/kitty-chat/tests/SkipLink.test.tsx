import { cleanup, render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'

import { SkipLink } from '../src/components/SkipLink'

afterEach(cleanup)

describe('SkipLink', () => {
  it('targets the main content landmark', () => {
    render(<SkipLink />)
    const link = screen.getByRole('link', { name: 'Skip to main content' })
    expect(link.getAttribute('href')).toBe('#main-content')
    expect(link.className).toContain('skip-link')
  })

  it('has a matching main-content target in the app shell', () => {
    const page = readFileSync(resolve(process.cwd(), 'src/app/page.tsx'), 'utf8')
    expect(page).toContain('<main id="main-content"')
  })
})
