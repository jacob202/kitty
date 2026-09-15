// Record which source revision produced .next, for every build path.
//
// `make ui-build` used to be the only thing that wrote this stamp, so a plain
// `npm run build` left provenance reporting a truthful but useless "unknown"
// and the running UI could not be tied to a commit. Chaining this to the build
// script closes that hole: a clean tree stamps the commit, a dirty tree stamps
// `dirty:<sha>`, which the doctor already reports as `dirty-built`. There is no
// build that leaves no stamp.

import { execFileSync } from 'node:child_process'
import { existsSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const uiDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const nextDir = join(uiDir, '.next')

const git = (...args) =>
  execFileSync('git', ['-C', uiDir, ...args], { encoding: 'utf8' }).trim()

if (!existsSync(nextDir)) {
  console.error('stamp-source-sha: no .next directory; nothing to stamp')
  process.exit(0)
}

try {
  const head = git('rev-parse', 'HEAD')
  const dirty = git('status', '--porcelain', '--untracked-files=normal', '--', '.') !== ''
  const stamp = dirty ? `dirty:${head}` : head
  writeFileSync(join(nextDir, 'KITTY_SOURCE_SHA'), `${stamp}\n`, 'utf8')
  console.log(`stamp-source-sha: ${stamp}`)
} catch (error) {
  // No git, no repository, or a detached toolchain: leave no stamp rather than
  // an invented one. The doctor reports that as "unknown", which is true.
  console.error(`stamp-source-sha: could not record source identity: ${error.message}`)
  process.exitCode = 1
}
