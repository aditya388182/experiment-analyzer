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

# ---------- frontend ----------
BASE_URL ?= http://localhost:5173
.PHONY: test-frontend lint-frontend run-web screenshots
test-frontend: ## Vitest + RTL + MSW
	cd frontend && npx vitest run

lint-frontend: ## tsc --noEmit and eslint with zero warnings
	cd frontend && npx tsc -b --noEmit && npx eslint --max-warnings 0 .

run-web: ## Vite dev server on 127.0.0.1:5173, proxying /api to 127.0.0.1:8000
	cd frontend && npx vite

screenshots: ## docs/screenshots from a running stack (needs PLAYWRIGHT_DIR with playwright@1.64.1 installed)
	node scripts/screenshots.mjs $(BASE_URL) docs/screenshots

# ---------- whole project ----------
COMPOSE := docker compose -f deploy/compose.dev.yml
.PHONY: python dev dev-down logs build-images test lint lint-python lint-helm ci results-tests
python: ## install CPython 3.12.16 for uv (DECISIONS.md D1)
	scripts/install_python.sh

dev: ## full Docker Compose stack: http://localhost:8080 (web), :8000 (api), :5000 (moto), :15672 (rabbitmq UI)
	GIT_SHA=$$(git rev-parse --short HEAD) $(COMPOSE) up -d --build --wait
	@echo "web http://localhost:8080   api http://localhost:8000/api/health   rabbitmq http://localhost:15672"

dev-down: ## stop the stack (keeps the postgres volume)
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker

build-images: ## build the api and web images
	docker build -f deploy/docker/api.Dockerfile --build-arg GIT_SHA=$$(git rev-parse --short HEAD) -t experiment-analyzer-api:local .
	docker build -f deploy/docker/web.Dockerfile -t experiment-analyzer-web:local .

test: test-abkit test-backend test-frontend ## abkit + backend + frontend tests (backend needs postgres + rabbitmq up)

lint-python: ## ruff check + format check
	cd abkit && uv run ruff check . && uv run ruff format --check .
	cd backend && uv run ruff check . && uv run ruff format --check .

lint-helm: ## helm lint + kubeconform (Kubernetes 1.36 schemas)
	scripts/helm_check.sh

lint: lint-python lint-frontend lint-helm ## ruff, eslint, tsc, helm lint, kubeconform

ci: lint test test-integration build-images ## the same checks as .github/workflows/ci.yml, run locally

results-tests: ## run every suite with JUnit output and write results/tests.json
	mkdir -p build
	cd abkit && uv run pytest -q --junitxml=../build/junit-abkit.xml
	cd backend && uv run pytest -q --junitxml=../build/junit-backend.xml
	JUNIT_XML=$(CURDIR)/build/junit-integration.xml scripts/integration.sh
	cd frontend && npx vitest run --reporter=default --reporter=junit --outputFile.junit=../build/junit-frontend.xml
	cd backend && uv run python ../scripts/test_counts.py ../build
