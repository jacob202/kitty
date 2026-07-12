.PHONY: agent-wrap test lint typecheck ci ui-test ui-build ui-tailnet smoke-test

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
