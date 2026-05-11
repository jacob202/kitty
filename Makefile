# Kitty — thin convenience targets. Port values are documented in docs/ARCHITECTURE.md
# (sourced from kitty_gateway/*.sh).

.PHONY: rebuild-index

rebuild-index:
	./venv/bin/python scripts/kitty_manage.py ingest data/knowledge
