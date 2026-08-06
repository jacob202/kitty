#!/usr/bin/env python3
"""Capture the current Kitty Work surface after passing first-run onboarding.

Run from the isolated proof worktree while the current Kitty UI is already
listening on 127.0.0.1:4000. This script makes no provider/model calls and does
not mutate Builder state.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd().resolve()
CHAT = ROOT / "gateway" / "kitty-chat"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = Path.home() / "Desktop" / f"kitty-work-surface-proof-{STAMP}"
ZIP_BASE = Path.home() / "Desktop" / f"kitty-work-surface-proof-{STAMP}"


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    if not (ROOT / ".git").exists() or not (CHAT / "package.json").exists():
        fail("run this from the isolated Kitty proof worktree")
    if not port_open(4000):
        fail("Kitty UI is not listening on port 4000")
    if not (CHAT / "node_modules" / "@playwright" / "test").exists():
        fail("Playwright is not installed in the isolated frontend")

    OUT.mkdir(parents=True)
    script = r'''
const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');
const out = process.env.KITTY_PROOF_OUT;

async function capture(name, viewport) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport });
  const evidence = {
    name,
    viewport,
    console: [],
    pageErrors: [],
    failedRequests: [],
    badResponses: [],
  };

  page.on('console', msg => {
    if (['error', 'warning'].includes(msg.type())) {
      evidence.console.push({ type: msg.type(), text: msg.text().slice(0, 1500) });
    }
  });
  page.on('pageerror', err => evidence.pageErrors.push(String(err).slice(0, 2000)));
  page.on('requestfailed', req => evidence.failedRequests.push({
    method: req.method(),
    url: req.url(),
    failure: req.failure(),
  }));
  page.on('response', res => {
    if (res.status() >= 400) evidence.badResponses.push({ status: res.status(), url: res.url() });
  });

  try {
    await page.goto('http://127.0.0.1:4000', { waitUntil: 'networkidle', timeout: 45000 });

    const dialog = page.getByRole('dialog', { name: /welcome to kitty/i });
    if (await dialog.count()) {
      evidence.onboardingVisible = true;
      await page.screenshot({ path: path.join(out, `${name}-onboarding.png`), fullPage: true });
      await dialog.getByRole('button', { name: /^continue$/i }).click();
      await page.waitForTimeout(750);
    } else {
      evidence.onboardingVisible = false;
    }

    let work = page.getByRole('button', { name: /^work$/i });
    if (await work.count() === 0) work = page.getByRole('link', { name: /^work$/i });
    if (await work.count() === 0) throw new Error('Work navigation control not found');

    await work.first().click();
    await page.waitForTimeout(3500);
    await page.screenshot({ path: path.join(out, `${name}-work.png`), fullPage: true });

    evidence.work = {
      url: page.url(),
      title: await page.title(),
      bodyText: (await page.locator('body').innerText()).slice(0, 30000),
      controls: await page.locator('button, a, [role="button"], [role="link"]').allInnerTexts(),
      documentWidth: await page.evaluate(() => document.documentElement.scrollWidth),
      viewportWidth: await page.evaluate(() => window.innerWidth),
    };
  } catch (error) {
    evidence.fatal = String(error);
  } finally {
    fs.writeFileSync(
      path.join(out, `${name}-evidence.json`),
      JSON.stringify(evidence, null, 2),
    );
    await browser.close();
  }
}

(async () => {
  await capture('desktop', { width: 1440, height: 900 });
  await capture('phone', { width: 393, height: 852 });
})().catch(error => {
  console.error(error);
  process.exit(1);
});
'''

    env = os.environ.copy()
    env["KITTY_PROOF_OUT"] = str(OUT)
    result = subprocess.run(
        ["node", "-e", script],
        cwd=CHAT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(result.stdout, end="")
    (OUT / "browser-capture.txt").write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        fail("browser capture failed")

    summary = {
        "worktree": str(ROOT),
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "spend_cad": 0.0,
        "builder_mutations": 0,
    }
    (OUT / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    archive = shutil.make_archive(str(ZIP_BASE), "zip", OUT.parent, OUT.name)
    print("COMPLETE")
    print(f"Upload this file: {archive}")


if __name__ == "__main__":
    main()
