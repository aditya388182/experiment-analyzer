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

# ---------- backend ----------
DEV_ENV := set -a && . ../scripts/dev.env && set +a
.PHONY: infra-up infra-down test-backend run-api run-worker curl-walkthrough
infra-up: ## start postgres, rabbitmq and moto only (127.0.0.1)
	docker compose -f deploy/compose.dev.yml up -d --wait postgres rabbitmq moto

infra-down:
	docker compose -f deploy/compose.dev.yml down

test-backend: ## backend unit tests (needs `make infra-up`; S3 is an in-test moto server)
	cd backend && uv run pytest -q -m "not integration"

run-api: ## API on the host against the infra containers
	cd backend && $(DEV_ENV) && uv run python manage.py migrate -v0 && uv run python manage.py createcachetable \
	  && uv run gunicorn config.wsgi -b 127.0.0.1:8000 -w 2 --access-logfile -

curl-walkthrough: ## Phase 2 check: presigned POST upload to moto via curl
	scripts/curl_walkthrough.sh

.PHONY: test-integration
test-integration: ## real RabbitMQ + Celery worker + API end to end (needs `make infra-up`)
	scripts/integration.sh
