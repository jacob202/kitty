/**
 * Visual diff harness for Kitty's UI.
 *
 * Boots a Playwright Chromium against the dev server, navigates to a fixed set
 * of routes, screenshots each, and compares against a baseline using pixelmatch.
 *
 * Usage:
 *   npx tsx scripts/visual-diff.ts                # compare to baseline
 *   npx tsx scripts/visual-diff.ts --update       # overwrite baselines
 *   npx tsx scripts/visual-diff.ts --threshold=0  # any pixel diff fails
 *
 * Output:
 *   data/visual-diffs/<branch>/<route>.png       # current screenshot
 *   data/visual-diffs/<branch>/<route>.baseline.png  # copied baseline (if different)
 *   data/visual-diffs/<branch>/<route>.diff.png  # pixel-difference overlay (only when different)
 *   data/visual-diffs/<branch>/summary.json      # aggregate diff stats
 *
 * The branch name defaults to `git rev-parse --abbrev-ref HEAD` so workers in
 * isolated worktrees report under their own branch.
 *
 * The harness pre-sets localStorage flags (kitty-onboarded=true, kitty-theme)
 * so screenshots are stable across runs. If a test needs the fresh-onboarding
 * state, add a separate route like `onboarding` with no pre-set.
 */

import { chromium, type Page } from '@playwright/test';
import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import Pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const BASELINE_DIR = join(ROOT, 'data', 'visual-baselines');
const DIFF_ROOT = join(ROOT, 'data', 'visual-diffs');

interface Route {
  name: string;
  path: string;
  setup?: (page: Page) => Promise<void>;
  viewport?: { width: number; height: number };
}

const DEFAULT_VIEWPORT = { width: 1280, height: 800 };
const MOBILE_VIEWPORT = { width: 390, height: 844 };

const ROUTES: Route[] = [
  {
    name: 'home-desktop',
    path: '/',
    viewport: DEFAULT_VIEWPORT,
    setup: async (page) => {
      await page.addInitScript(() => {
        window.localStorage.setItem('kitty-onboarded', 'true');
        window.localStorage.setItem('kitty-theme', 'cosmic');
      });
    },
  },
  {
    name: 'home-mobile',
    path: '/',
    viewport: MOBILE_VIEWPORT,
    setup: async (page) => {
      await page.addInitScript(() => {
        window.localStorage.setItem('kitty-onboarded', 'true');
        window.localStorage.setItem('kitty-theme', 'cosmic');
      });
    },
  },
  {
    name: 'onboarding-fresh',
    path: '/',
    viewport: DEFAULT_VIEWPORT,
    // No setup; the page should render the onboarding modal.
  },
];

async function currentBranch(): Promise<string> {
  try {
    return execSync('git rev-parse --abbrev-ref HEAD', { cwd: ROOT, encoding: 'utf8' }).trim();
  } catch {
    return 'detached';
  }
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function ensureDir(path: string): Promise<void> {
  await mkdir(path, { recursive: true });
}

interface Summary {
  branch: string;
  updated: boolean;
  threshold: number;
  routes: RouteResult[];
}

interface RouteResult {
  name: string;
  path: string;
  status: 'unchanged' | 'changed' | 'new' | 'updated';
  baseline_path?: string;
  current_path?: string;
  diff_path?: string;
  diff_ratio?: number;
  pixel_diff?: number;
  pixel_total?: number;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const update = args.includes('--update');
  const thresholdArg = args.find((a) => a.startsWith('--threshold='));
  const threshold = thresholdArg ? parseFloat(thresholdArg.split('=')[1]) : 0.001; // 0.1% by default

  const baseUrl = process.env.VISUAL_DIFF_BASE_URL ?? 'http://localhost:4000';
  const branch = await currentBranch();
  const diffDir = join(DIFF_ROOT, branch);

  await ensureDir(BASELINE_DIR);
  await ensureDir(diffDir);

  const browser = await chromium.launch();
  const summary: Summary = { branch, updated: update, threshold, routes: [] };

  for (const route of ROUTES) {
    const baselinePath = join(BASELINE_DIR, `${route.name}.png`);
    const currentPath = join(diffDir, `${route.name}.png`);
    const diffPath = join(diffDir, `${route.name}.diff.png`);

    const context = await browser.newContext({ viewport: route.viewport ?? DEFAULT_VIEWPORT });
    const page = await context.newPage();
    await route.setup?.(page);

    // Hard navigation cap. The chat keeps an SSE stream open for runtime
    // updates, so most "wait for load" predicates never fire. We give the
    // initial paint 5 seconds, then proceed regardless. The fixed settle
    // wait below handles the rest.
    try {
      await page.goto(baseUrl + route.path, { waitUntil: 'commit', timeout: 5_000 });
    } catch {
      // commit = "got first byte"; load/domcontentloaded/networkidle all hang
      // because SSE keeps the connection open.
    }

    // Wait for the React root to actually render something before screenshotting.
    try {
      await page.waitForSelector('main, [role="dialog"], body', { timeout: 5_000 });
    } catch {
      // If nothing appears, screenshot the blank page — still useful.
    }

    await page.waitForTimeout(1500); // settle streaming + first paint
    await page.screenshot({ path: currentPath, fullPage: false });
    await context.close();

    const hasBaseline = await fileExists(baselinePath);
    const result: RouteResult = {
      name: route.name,
      path: route.path,
      status: 'new',
      current_path: currentPath,
    };

    if (!hasBaseline) {
      if (update) {
        await writeFile(baselinePath, await readFile(currentPath));
        result.status = 'updated';
        result.baseline_path = baselinePath;
        delete result.current_path;
      } else {
        result.status = 'new';
      }
      summary.routes.push(result);
      continue;
    }

    const baselinePng = PNG.sync.read(await readFile(baselinePath));
    const currentPng = PNG.sync.read(await readFile(currentPath));
    if (baselinePng.width !== currentPng.width || baselinePng.height !== currentPng.height) {
      throw new Error(
        `Dimensions mismatch for ${route.name}: baseline ${baselinePng.width}x${baselinePng.height} vs current ${currentPng.width}x${currentPng.height}. Use --update to reset the baseline after an intentional change.`,
      );
    }

    const diff = new PNG({ width: baselinePng.width, height: baselinePng.height });
    const pixelDiff = Pixelmatch(
      baselinePng.data,
      currentPng.data,
      diff.data,
      baselinePng.width,
      baselinePng.height,
      { threshold },
    );
    const pixelTotal = baselinePng.width * baselinePng.height;
    const diffRatio = pixelDiff / pixelTotal;

    result.baseline_path = baselinePath;
    result.diff_path = diffPath;
    result.pixel_diff = pixelDiff;
    result.pixel_total = pixelTotal;
    result.diff_ratio = diffRatio;

    if (update) {
      await writeFile(baselinePath, await readFile(currentPath));
      result.status = 'updated';
      delete result.diff_path;
    } else if (pixelDiff === 0) {
      result.status = 'unchanged';
      delete result.diff_path;
      delete result.diff_path;
      try {
        await writeFile(diffPath, PNG.sync.write(diff));
      } catch {
        // best-effort; not relevant when unchanged
      }
    } else {
      result.status = 'changed';
      await writeFile(diffPath, PNG.sync.write(diff));
    }

    summary.routes.push(result);
  }

  await browser.close();

  await writeFile(join(diffDir, 'summary.json'), JSON.stringify(summary, null, 2));

  const changedRoutes = summary.routes.filter((r) => r.status === 'changed');
  const newRoutes = summary.routes.filter((r) => r.status === 'new');

  // eslint-disable-next-line no-console
  console.log(`\nvisual-diff summary — branch: ${branch}, ${update ? 'UPDATE mode' : 'compare mode'}`);
  for (const r of summary.routes) {
    const line =
      r.status === 'unchanged'
        ? `  ${r.name}: unchanged`
        : r.status === 'updated'
          ? `  ${r.name}: baseline updated`
          : r.status === 'new'
            ? `  ${r.name}: NEW (no baseline${update ? ' — written' : ' — run with --update'})`
            : `  ${r.name}: CHANGED ${r.pixel_diff}/${r.pixel_total} (${(r.diff_ratio! * 100).toFixed(2)}%)`;
    // eslint-disable-next-line no-console
    console.log(line);
  }

  if (!update && (changedRoutes.length > 0 || newRoutes.length > 0)) {
    // eslint-disable-next-line no-console
    console.error(
      `\n${changedRoutes.length} changed + ${newRoutes.length} new routes. See ${diffDir}.`,
    );
    process.exit(1);
  }
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(2);
});

// Hard outer watchdog so the script can never hang past its budget.
// Some pages (chat, repairs) hold SSE streams that prevent most wait
// predicates from firing; we already work around that inside main(),
// but if something else deadlocks we still want to fail loud and exit.
const HARD_TIMEOUT_MS = 120_000;
setTimeout(() => {
  // eslint-disable-next-line no-console
  console.error(`visual-diff: hard timeout after ${HARD_TIMEOUT_MS / 1000}s, exiting`);
  process.exit(3);
}, HARD_TIMEOUT_MS).unref();