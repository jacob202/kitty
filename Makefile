.PHONY: agent-wrap vibe-session test lint typecheck ci ui-test ui-build ui-tailnet smoke-test codegraph-check visual-diff visual-diff-update swarm-review healthcheck preview diff-pr trust-eval

agent-wrap:
	python3.12 scripts/agent_wrapup.py

vibe-session:
	@if [ -z "$$OUTCOME" ]; then echo "usage: make vibe-session OUTCOME='... ' [MINUTES=60]"; exit 2; fi
	python3.12 scripts/vibe_session.py "$$OUTCOME" --minutes $${MINUTES:-60}

test:
	python3.12 -m pytest tests/ -q --tb=short

# Mirrors the pytest job's coverage gate. `test` stays uncovered so the
# narrow-test loop during development is not slowed by instrumentation.
test-ci:
	python3.12 -m pytest tests/ -q --tb=short \
		--cov=gateway --cov-report=term-missing --cov-fail-under=73

# Paths match the lint and typecheck jobs exactly. They were narrower than CI,
# so `make ci` could pass on code the Tests workflow would reject.
lint:
	./venv/bin/ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py

typecheck:
	python3.12 -m mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py

ci: lint typecheck test-ci ui-test ui-build

smoke-test:
	cd gateway/kitty-chat && npx playwright test

ui-test:
	cd gateway/kitty-chat && ./node_modules/.bin/vitest run

ui-build:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next build

ui-tailnet:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next dev -H 0.0.0.0 -p 4000

visual-diff:
	cd gateway/kitty-chat && npx tsx scripts/visual-diff.ts

visual-diff-update:
	cd gateway/kitty-chat && npx tsx scripts/visual-diff.ts --update

swarm-review:
	cd gateway/kitty-chat && npx tsx scripts/swarm-review.ts

dogfood:
	cd gateway/kitty-chat && npx tsx scripts/dogfood.ts

healthcheck:
	./kitty doctor --json | python3.12 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('summary',{}).get('fail',0)==0 else 1)"
	./kitty builder initiative doctor --json | python3.12 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)"

# Run the live Kitty trust regression suite against the local Gateway.
# This is deliberately opt-in because it invokes the configured model route and
# may consume provider credits. Results stay under ignored data/ runtime state.
trust-eval:
	@if [ "$$KITTY_LIVE_EVAL" != "1" ]; then \
		echo "Refusing live model calls. Re-run with: KITTY_LIVE_EVAL=1 make trust-eval"; \
		exit 2; \
	fi
	@BASE_URL="$${KITTY_EVAL_BASE_URL:-http://127.0.0.1:8000}"; \
	SECRET="$${GATEWAY_SECRET:-$$(python3.12 -c 'import os; from dotenv import load_dotenv; load_dotenv(".env"); print(os.getenv("GATEWAY_SECRET", ""))')}"; \
	if [ -z "$$SECRET" ]; then \
		echo "GATEWAY_SECRET is unavailable. Configure it in .env before running live evals."; \
		exit 1; \
	fi; \
	curl -fsS "$$BASE_URL/health" >/dev/null || { \
		echo "Kitty Gateway is not healthy at $$BASE_URL/health. Run ./kitty up first."; \
		exit 1; \
	}; \
	mkdir -p data/promptfoo; \
	GATEWAY_SECRET="$$SECRET" \
	KITTY_EVAL_BASE_URL="$$BASE_URL" \
	KITTY_EVAL_MODEL="$${KITTY_EVAL_MODEL:-kitty-default}" \
	PROMPTFOO_CONFIG_DIR="$(CURDIR)/data/promptfoo" \
	PROMPTFOO_CACHE_PATH="$(CURDIR)/data/promptfoo/cache" \
	PROMPTFOO_DISABLE_TELEMETRY=1 \
	PROMPTFOO_DISABLE_UPDATE=1 \
	PROMPTFOO_EVAL_TIMEOUT_MS=60000 \
	PROMPTFOO_MAX_EVAL_TIME_MS=600000 \
	npx --yes promptfoo@0.121.19 eval \
		-c evals/kitty/promptfooconfig.json \
		--no-cache \
		-j 1 \
		--output data/promptfoo/kitty-trust-latest.json

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
