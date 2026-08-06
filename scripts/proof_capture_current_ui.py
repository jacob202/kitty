#!/usr/bin/env python3
"""Capture current Kitty UI evidence from an isolated proof worktree.

This script performs no provider/model calls and does not mutate Builder state.
It replaces only an invalid node_modules symlink inside the current worktree,
installs the pinned frontend dependencies, builds the UI, starts the production
server, and captures Home/Work evidence at desktop and phone viewports.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path.cwd().resolve()
CHAT = ROOT / "gateway" / "kitty-chat"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = Path.home() / "Desktop" / f"kitty-current-ui-proof-{STAMP}"
ZIP_BASE = Path.home() / "Desktop" / f"kitty-current-ui-proof-{STAMP}"


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(name: str, command: list[str], *, cwd: Path) -> None:
    print(f"\n=== {name} ===")
    print("$", " ".join(command))
    log_path = OUT / f"{name.lower().replace(' ', '-')}.txt"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)
        code = process.wait()
    if code != 0:
        fail(f"{name} exited with code {code}; see {log_path}")


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_ui(seconds: int = 60) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urlopen("http://127.0.0.1:4000", timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(1)
    fail("Kitty UI did not become ready on port 4000")


def capture_browser() -> None:
    script = r'''
const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');
const out = process.env.KITTY_PROOF_OUT;

async function capture(name, viewport) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport });
  const evidence = { name, viewport, console: [], pageErrors: [], failedRequests: [], badResponses: [] };
  page.on('console', msg => {
    if (['error', 'warning'].includes(msg.type())) evidence.console.push({ type: msg.type(), text: msg.text().slice(0, 1500) });
  });
  page.on('pageerror', err => evidence.pageErrors.push(String(err).slice(0, 2000)));
  page.on('requestfailed', req => evidence.failedRequests.push({ method: req.method(), url: req.url(), failure: req.failure() }));
  page.on('response', res => {
    if (res.status() >= 400) evidence.badResponses.push({ status: res.status(), url: res.url() });
  });

  try {
    await page.goto('http://127.0.0.1:4000', { waitUntil: 'networkidle', timeout: 45000 });
    await page.screenshot({ path: path.join(out, `${name}-home.png`), fullPage: true });
    evidence.home = {
      url: page.url(),
      title: await page.title(),
      bodyText: (await page.locator('body').innerText()).slice(0, 18000),
      controls: await page.locator('button, a, [role="button"], [role="link"]').allInnerTexts(),
      documentWidth: await page.evaluate(() => document.documentElement.scrollWidth),
      viewportWidth: await page.evaluate(() => window.innerWidth),
    };

    let work = page.getByRole('button', { name: /^work$/i });
    if (await work.count() === 0) work = page.getByRole('link', { name: /^work$/i });
    if (await work.count() === 0) throw new Error('Work navigation control not found');
    await work.first().click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(out, `${name}-work.png`), fullPage: true });
    evidence.work = {
      url: page.url(),
      bodyText: (await page.locator('body').innerText()).slice(0, 24000),
      controls: await page.locator('button, a, [role="button"], [role="link"]').allInnerTexts(),
      documentWidth: await page.evaluate(() => document.documentElement.scrollWidth),
      viewportWidth: await page.evaluate(() => window.innerWidth),
    };
  } catch (error) {
    evidence.fatal = String(error);
  } finally {
    fs.writeFileSync(path.join(out, `${name}-evidence.json`), JSON.stringify(evidence, null, 2));
    await browser.close();
  }
}

(async () => {
  await capture('desktop', { width: 1440, height: 900 });
  await capture('phone', { width: 393, height: 852 });
})().catch(error => { console.error(error); process.exit(1); });
'''
    env = os.environ.copy()
    env["KITTY_PROOF_OUT"] = str(OUT)
    print("\n=== Browser capture ===")
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


def main() -> None:
    if not (ROOT / ".git").exists() or not (CHAT / "package.json").exists():
        fail("run this from the root of the isolated Kitty proof worktree")

    OUT.mkdir(parents=True)
    print("Kitty current UI proof")
    print(f"Worktree: {ROOT}")
    print(f"Evidence: {OUT}")
    print("Spend: $0.00 CAD")

    node_modules = CHAT / "node_modules"
    if node_modules.is_symlink():
        target = node_modules.resolve(strict=False)
        print(f"Removing invalid worktree node_modules symlink -> {target}")
        node_modules.unlink()
    elif node_modules.exists() and not node_modules.is_dir():
        fail(f"unexpected node_modules object: {node_modules}")

    run("Frontend install", ["npm", "ci"], cwd=CHAT)
    run("Frontend build", ["npm", "run", "build"], cwd=CHAT)

    if port_open(4000):
        fail("port 4000 is already occupied; no process was killed")

    ui_log = (OUT / "kitty-ui.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["npm", "start"],
        cwd=CHAT,
        stdout=ui_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )
    (OUT / "kitty-ui.pid").write_text(f"{process.pid}\n", encoding="utf-8")
    wait_for_ui()

    capture_browser()

    status = subprocess.run(
        [str(ROOT / "kitty"), "status"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print("\n=== Kitty status ===")
    print(status.stdout, end="")
    (OUT / "kitty-status.txt").write_text(status.stdout, encoding="utf-8")

    summary = {
        "worktree": str(ROOT),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ui_pid": process.pid,
        "spend_cad": 0.0,
    }
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    archive = shutil.make_archive(str(ZIP_BASE), "zip", OUT.parent, OUT.name)
    print("\nCOMPLETE")
    print(f"Upload this file: {archive}")


if __name__ == "__main__":
    main()
