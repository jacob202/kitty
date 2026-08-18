import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const source = fs.readFileSync(path.resolve(__dirname, '../src/components/StudioView.tsx'), 'utf8')

describe('Studio product surface', () => {
  it('uses one dedicated Image Lab instead of separate gallery and generate products', () => {
    expect(source).toContain("import { ImageLab } from '@/components/ImageLab'")
    expect(source).toContain('<ImageLab />')
    expect(source).not.toContain('ImageGenPanel')
    expect(source).not.toContain("setTab(")
    expect(source).not.toContain("{ id: 'gallery'")
  })
})
