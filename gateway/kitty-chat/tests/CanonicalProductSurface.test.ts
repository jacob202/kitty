import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const root = path.resolve(__dirname, '../src')
const renderer = fs.readFileSync(path.join(root, 'components/ViewRenderer.tsx'), 'utf8')
const studio = fs.readFileSync(path.join(root, 'components/StudioView.tsx'), 'utf8')

describe('canonical native product surface', () => {
  it('keeps only the reachable agent and image surfaces', () => {
    expect(renderer).toContain('AgentWorkspacePanel')
    expect(studio).toContain('ImageLab')

    for (const relative of [
      'components/AgentPanel.tsx',
      'components/ImageGenPanel.tsx',
      'components/ImageStudio.tsx',
      'hooks/useViewRouter.ts',
    ]) {
      expect(fs.existsSync(path.join(root, relative)), relative).toBe(false)
    }
  })
})
