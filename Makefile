.PHONY: agent-wrap ui-test ui-build ui-tailnet

agent-wrap:
	python3.12 scripts/agent_wrapup.py

ui-test:
	cd gateway/kitty-chat && ./node_modules/.bin/vitest run

ui-build:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next build

# Bind the UI on all interfaces so the phone can reach it over Tailscale.
# The gateway stays loopback-only; the Next proxy talks to it server-side.
ui-tailnet:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next dev -H 0.0.0.0 -p 4000
