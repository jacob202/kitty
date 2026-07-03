.PHONY: agent-wrap ui-test ui-build

agent-wrap:
	python3.12 scripts/agent_wrapup.py

ui-test:
	cd gateway/kitty-chat && ./node_modules/.bin/vitest run

ui-build:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next build
