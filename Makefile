# experiment-analyzer. Run `make help`.
SHELL := /bin/bash
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: help
help:
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | sort

# ---------- abkit ----------
.PHONY: test-abkit results-abkit
test-abkit: ## abkit tests
	cd abkit && uv run pytest -q

results-abkit: ## abkit tests, writing results/validation.json and results/lab_reproduction.json
	cd abkit && ABKIT_WRITE_RESULTS=1 ABKIT_RESULTS_COMMAND="make results-abkit" uv run pytest -q
