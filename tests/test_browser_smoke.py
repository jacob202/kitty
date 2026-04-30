"""Browser smoke tests for the Kitty web app.

Starts a live Flask/SocketIO server on port 5099 and drives it with
Playwright (Chromium). Skipped automatically when playwright is not
installed so the regular unit-test run is never broken by a missing
browser dependency.

Install requirements (once):
    venv/bin/python -m pip install playwright pytest-playwright
    venv/bin/python -m playwright install chromium

Run just these tests:
    venv/bin/python -m pytest tests/test_browser_smoke.py -v
"""

from __future__ import annotations

import threading
import time

import pytest

try:
    from playwright.sync_api import Page, expect
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _PLAYWRIGHT_AVAILABLE,
    reason="playwright not installed — run: pip install playwright pytest-playwright && playwright install chromium",
)

BASE_URL = "http://127.0.0.1:5099"


@pytest.fixture(scope="session")
def live_app():
    """Start the Kitty Flask/SocketIO app in a background daemon thread."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from web import create_app

    app, socketio = create_app()
    app.config["TESTING"] = True

    def run():
        socketio.run(app, host="127.0.0.1", port=5099, use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(2)
    yield app


@pytest.fixture(scope="session")
def browser_context(live_app):
    """Single Playwright browser context shared across all session tests."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture()
def page(browser_context):
    """Fresh page per test; context is reused for speed."""
    p = browser_context.new_page()
    yield p
    p.close()


def test_page_loads(page: "Page"):
    """Home page must return something other than a 500 error."""
    response = page.goto(BASE_URL, wait_until="domcontentloaded")
    assert response is not None
    assert response.status < 500, f"Server returned HTTP {response.status}"
    expect(page.locator("body")).not_to_be_empty()


def test_chat_input_exists(page: "Page"):
    """Chat input (textarea#inp) must be visible."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    expect(page.locator("#inp")).to_be_visible(timeout=5_000)


def test_mic_button_exists(page: "Page"):
    """Voice/mic button (#voice-toggle) must be visible."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    expect(page.locator("#voice-toggle")).to_be_visible(timeout=5_000)


def test_page_has_no_js_errors(page: "Page"):
    """Page must not show an Application Error crash banner."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    assert "Application Error" not in page.locator("body").inner_text()
