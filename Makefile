.PHONY: agent-wrap test lint typecheck ci ui-test ui-build ui-tailnet smoke-test codegraph-check

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

codegraph-check:
	@if [ ! -f .codegraph/codegraph.db ]; then \
		echo "WARNING: codegraph index not initialized. Run: codegraph init"; \
	elif [ "$$(find .codegraph/codegraph.db -mtime +7 2>/dev/null)" ]; then \
		echo "WARNING: codegraph index is over 7 days old. Consider regenerating."; \
	else \
		echo "codegraph index: fresh"; \
	fi
