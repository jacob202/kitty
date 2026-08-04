import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const packagePath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  'package.json'
)
const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8')) as {
  scripts: Record<string, string>
}

describe('kitty-chat listener security', () => {
  it('binds supported development and production commands to loopback', () => {
    expect(packageJson.scripts.dev).toContain('-H 127.0.0.1')
    expect(packageJson.scripts.start).toContain('-H 127.0.0.1')
  })

  it('does not expose an unauthenticated tailnet or all-interface command', () => {
    expect(packageJson.scripts).not.toHaveProperty('dev:tailnet')
    expect(packageJson.scripts).not.toHaveProperty('start:tailnet')
    expect(Object.values(packageJson.scripts).join('\n')).not.toContain('0.0.0.0')
  })
})
