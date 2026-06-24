.PHONY: agent-wrap test test-full test-fast

# Default test target: skips slow (real mem0 / network / I/O) tests.
# Use `make test-full` to run everything; that's what CI should use.
test:
	python3.12 -m pytest tests/ -q --tb=short

# Same as `make test` — explicit alias for clarity.
test-fast: test

# Full suite: includes real mem0, network, I/O. Run before shipping.
test-full:
	python3.12 -m pytest tests/ -q --tb=short -m ""

agent-wrap:
	python3.12 scripts/agent_wrapup.py
