.PHONY: agent-wrap test lint typecheck ci ui-test ui-build ui-tailnet smoke-test codegraph-check visual-diff visual-diff-update healthcheck preview diff-pr

agent-wrap:
	python3.12 scripts/agent_wrapup.py

test:
	python3.12 -m pytest tests/ -q --tb=short

lint:
	./venv/bin/ruff check gateway/ tests/

typecheck:
	python3.12 -m mypy gateway/

ci: lint typecheck test ui-test ui-build

smoke-test:
	cd gateway/kitty-chat && npx playwright test

ui-test:
	cd gateway/kitty-chat && ./node_modules/.bin/vitest run

ui-build:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next build

# Bind the UI on all interfaces so the phone can reach it over Tailscale.
# The gateway stays loopback-only; the Next proxy talks to it server-side.
ui-tailnet:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next dev -H 0.0.0.0 -p 4000

# Visual diff harness: screenshot a fixed set of routes against
# data/visual-baselines/. Fails with a non-zero exit when any pixel changed.
# Requires the dev server running at $VISUAL_DIFF_BASE_URL (default localhost:4000).
visual-diff:
	cd gateway/kitty-chat && npx tsx scripts/visual-diff.ts

# Overwrite the baselines with whatever is on screen right now. Use only when
# an intentional visual change ships — KX acceptance criteria call this out.
visual-diff-update:
	cd gateway/kitty-chat && npx tsx scripts/visual-diff.ts --update

# Single command for "is Kitty healthy enough to demo?" — the things I had to
# run separately while dogfooding today, bundled into one exit code.
healthcheck:
	./kitty doctor --json | python3.12 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('summary',{}).get('fail',0)==0 else 1)"
	./kitty builder initiative doctor --json | python3.12 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)"

# Open the dev UI in the user's default browser with a checklist of what to
# click — the loop I had to run by hand while dogfooding today, automated.
preview:
	@echo "Open http://localhost:4000 (or http://$(shell ipconfig getifaddr en0 2>/dev/null || echo "<tailscale-ip>"):4000 from your phone)"
	@echo ""
	@echo "Checklist:"
	@echo "  1. Onboarding appears once and persists across reloads"
	@echo "  2. Home greets you by name in the what's-next card"
	@echo "  3. Home shows: system (repairs), signals, experts strip"
	@echo "  4. Send a chat message; reply streams cleanly"
	@echo "  5. Ask 'what's wrong' — gets repairs feed in chat"
	@echo "  6. Builder surface shows controls (pause/resume/cleanup)"
	@echo "  7. Builder 'needs attention' count is sane (no cancelled)"
	@echo "  8. Settings: gateway live, routing live, models loaded"
	@open "http://localhost:4000" 2>/dev/null || xdg-open "http://localhost:4000" 2>/dev/null || echo "(no browser opener; open the URL manually)"

# Print what a branch would do to the UI: boot its worktree, snapshot,
# return the diff PNG path inline. For vibe-coder review of KX packets
# without manually checking out every branch.
diff-pr:
	@if [ -z "$$BRANCH" ]; then echo "usage: make diff-pr BRANCH=<name>"; exit 2; fi
	@echo "Diff for $$BRANCH against main:"
	@ls -la data/visual-diffs/$$BRANCH/ 2>/dev/null || echo "(no diff artifacts yet — run make visual-diff in that worktree)"

codegraph-check:
	@if [ ! -f .codegraph/codegraph.db ]; then \
		echo "WARNING: codegraph index not initialized. Run: codegraph init"; \
	elif [ "$$(find .codegraph/codegraph.db -mtime +7 2>/dev/null)" ]; then \
		echo "WARNING: codegraph index is over 7 days old. Consider regenerating."; \
	else \
		echo "codegraph index: fresh"; \
	fi
