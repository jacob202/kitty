/**
 * Swarm review harness — automated UI code review for Kitty.
 *
 * Scans all components for design-system violations, accessibility gaps,
 * mobile responsiveness issues, and common UI bugs. Produces a structured
 * JSON report. Designed to run in CI or as a pre-commit guard.
 *
 * Usage:
 *   npx tsx scripts/swarm-review.ts                    # scan all files
 *   npx tsx scripts/swarm-review.ts --quiet             # only print errors
 *   npx tsx scripts/swarm-review.ts --check <file>      # scan one file
 *
 * Output: data/swarm-reviews/<timestamp>.json
 * Exit: 0 if no findings, 1 if any violations found.
 */

import { readFile, writeFile, mkdir, readdir, stat } from 'node:fs/promises';
import { join, resolve, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SRC_DIR = join(ROOT, 'src');
const REVIEW_OUT = resolve(ROOT, '..', '..', '..', 'data', 'swarm-reviews');

// ── Rule definitions ────────────────────────────────────────────────────────

interface Finding {
  rule: string;
  severity: 'error' | 'warning' | 'info';
  file: string;
  line: number;
  message: string;
  snippet: string;
}

interface Review {
  timestamp: string;
  files_scanned: number;
  total_findings: number;
  findings: Finding[];
}

const RULES = {
  /** Lowercase copy — no capitalized UI strings in component renders. */
  NO_CAPITALIZED_UI: {
    id: 'no-capitalized-ui',
    description: 'UI copy should be lowercase per design canon',
    severity: 'warning' as const,
    check(content: string, file: string): Finding[] {
      const findings: Finding[] = [];
      const lines = content.split('\n');
      const capitalizedPatterns = />\s*[A-Z][a-z]+(\s+[A-Z][a-z]+)+\s*</g;
      const excluded = ['KittyThread', 'ChatMessage', 'CatCorner', 'CatBody',
        'CrayonCat', 'ErrorBoundary', 'KittyRuntimeProvider'];

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim().startsWith('//') || line.trim().startsWith('*')) continue;

        const matches = line.matchAll(capitalizedPatterns);
        for (const m of matches) {
          const text = m[0].replace(/[<>]/g, '').trim();
          if (excluded.some(e => text.includes(e))) continue;
          if (text.includes('<!--') || text.includes('-->')) continue;
          findings.push({
            rule: 'no-capitalized-ui',
            severity: 'warning',
            file,
            line: i + 1,
            message: `capitalized UI string: "${text}" — should be lowercase per design canon`,
            snippet: line.trim(),
          });
        }
      }
      return findings;
    },
  },

  /** No exclamation marks in product copy. */
  NO_EXCLAMATION_MARKS: {
    id: 'no-exclamation',
    description: 'No exclamation marks in product copy',
    severity: 'warning' as const,
    check(_content: string, _file: string): Finding[] {
      const findings: Finding[] = [];
      const lines = _content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim().startsWith('//') || line.trim().startsWith('*')) continue;
        if (line.trim().startsWith('import ')) continue;
        const textContent = line.match(/>([^<]*)</g);
        if (textContent) {
          for (const tc of textContent) {
            const text = tc.replace(/[<>]/g, '');
            if (text.includes('!')) {
              findings.push({
                rule: 'no-exclamation',
                severity: 'warning',
                file: _file,
                line: i + 1,
                message: `exclamation mark in product copy: "${text}"`,
                snippet: line.trim(),
              });
            }
          }
        }
      }
      return findings;
    },
  },

  /** Interactive elements must have accessible labels. */
  REQUIRES_ARIA_LABEL: {
    id: 'requires-aria-label',
    description: 'Interactive elements need aria-label for accessibility',
    severity: 'error' as const,
    check(content: string, file: string): Finding[] {
      const findings: Finding[] = [];
      const lines = content.split('\n');

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const nextLine = (lines[i + 1] ?? '').trim();

        // Skip if this line or next has an accessible label via title/aria/text
        const combined = (line + ' ' + nextLine).toLowerCase();
        if (combined.includes('aria-label') ||
            combined.includes('aria-labelledby') ||
            combined.includes('title=') ||
            combined.includes('{...props}') ||
            combined.includes('role=') ||
            combined.includes('alt=') ||
            combined.includes('placeholder=')) continue;

        // Check for standalone interactive tags
        const tagMatch = line.match(/<(button|a\s|input|select|textarea)(?:\s|>)/i);
        if (!tagMatch) continue;

        // Has visible text content? (rough check — text between > and next tag)
        if (/>[A-Za-z]/.test(line)) continue;

        findings.push({
          rule: 'requires-aria-label',
          severity: 'error',
          file,
          line: i + 1,
          message: `interactive <${tagMatch[1].trim()}> element missing accessible label`,
          snippet: line.trim(),
        });
      }
      return findings;
    },
  },

  /** Mobile responsiveness — check for safe-area handling. */
  MOBILE_SAFE_AREA: {
    id: 'mobile-safe-area',
    description: 'Bottom-positioned elements should handle safe-area-inset-bottom',
    severity: 'info' as const,
    check(content: string, file: string): Finding[] {
      const findings: Finding[] = [];
      const lines = content.split('\n');

      const hasSafeArea = content.includes('safe-area-inset-bottom');
      const hasBottomPosition = content.includes("bottom:") ||
        content.includes("paddingBottom:") ||
        content.includes("marginBottom:");

      if (hasBottomPosition && !hasSafeArea) {
        findings.push({
          rule: 'mobile-safe-area',
          severity: 'info',
          file,
          line: 1,
          message: 'file uses bottom positioning but does not handle safe-area-inset-bottom',
          snippet: 'n/a',
        });
      }
      return findings;
    },
  },

  /** Font usage — mono should only be used for data, timestamps, numbers. */
  FONT_MONO_AUDIT: {
    id: 'font-mono-audit',
    description: 'Mono font should only be used for data/numbers/timestamps',
    severity: 'info' as const,
    check(content: string, file: string): Finding[] {
      const findings: Finding[] = [];
      const lines = content.split('\n');

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.includes('--font-mono') && line.includes('children')) {
          findings.push({
            rule: 'font-mono-audit',
            severity: 'info',
            file,
            line: i + 1,
            message: 'mono font used on children prop — verify it renders data, not prose',
            snippet: line.trim(),
          });
        }
      }
      return findings;
    },
  },

  /** Viewport height — check for 100vh without fallback. */
  VIEWPORT_UNITS: {
    id: 'viewport-units',
    description: '100vh should use dvh or have a fallback for mobile browsers',
    severity: 'info' as const,
    check(content: string, file: string): Finding[] {
      const findings: Finding[] = [];
      const lines = content.split('\n');

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.includes('100vh') && !line.includes('dvh') && !line.includes('-webkit-fill')) {
          findings.push({
            rule: 'viewport-units',
            severity: 'info',
            file,
            line: i + 1,
            message: '100vh used without dvh fallback — may cause mobile viewport issues',
            snippet: line.trim(),
          });
        }
      }
      return findings;
    },
  },
};

// ── Scanner ──────────────────────────────────────────────────────────────────

async function* walkFiles(dir: string): AsyncGenerator<string> {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.next') continue;
      yield* walkFiles(full);
    } else if (extname(entry.name) === '.tsx' || extname(entry.name) === '.ts') {
      yield full;
    }
  }
}

async function scan(): Promise<Review> {
  const findings: Finding[] = [];
  let filesScanned = 0;

  for await (const filePath of walkFiles(SRC_DIR)) {
    const relativePath = filePath.replace(ROOT + '/', '');
    const content = await readFile(filePath, 'utf8');
    filesScanned++;

    for (const rule of Object.values(RULES)) {
      const result = rule.check(content, relativePath);
      findings.push(...result);
    }
  }

  return {
    timestamp: new Date().toISOString(),
    files_scanned: filesScanned,
    total_findings: findings.length,
    findings,
  };
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const quiet = args.includes('--quiet');
  const checkFile = args.find(a => a.startsWith('--check='));

  let review: Review;

  if (checkFile) {
    const filePath = resolve(checkFile.split('=')[1]);
    const content = await readFile(filePath, 'utf8');
    const findings: Finding[] = [];
    for (const rule of Object.values(RULES)) {
      findings.push(...rule.check(content, filePath));
    }
    review = {
      timestamp: new Date().toISOString(),
      files_scanned: 1,
      total_findings: findings.length,
      findings,
    };
  } else {
    review = await scan();
  }

  await mkdir(REVIEW_OUT, { recursive: true });
  const outFile = join(REVIEW_OUT, `${review.timestamp.replace(/[:.]/g, '-')}.json`);
  await writeFile(outFile, JSON.stringify(review, null, 2));

  const errors = review.findings.filter(f => f.severity === 'error');
  const warnings = review.findings.filter(f => f.severity === 'warning');
  const infos = review.findings.filter(f => f.severity === 'info');

  if (!quiet) {
    console.log(`\nswarm-review — ${review.files_scanned} files scanned`);
    console.log(`  ${errors.length} errors, ${warnings.length} warnings, ${infos.length} info`);
    console.log();
  }

  for (const f of review.findings) {
    if (quiet && f.severity === 'info') continue;
    const icon = f.severity === 'error' ? '✗' : f.severity === 'warning' ? '!' : 'i';
    console.log(`  ${icon} ${f.file}:${f.line} [${f.rule}] ${f.message}`);
    if (!quiet) console.log(`    ${f.snippet}`);
  }

  if (!quiet) {
    console.log(`\nfull report: ${outFile}`);
  }

  if (errors.length > 0) {
    console.error(`\n${errors.length} error(s) found.`);
    process.exit(1);
  }
}

main().catch(err => {
  console.error(err);
  process.exit(2);
});
