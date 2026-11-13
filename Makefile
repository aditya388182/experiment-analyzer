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
	cd backend && uv run ruff check ../scripts && uv run ruff format --check ../scripts

lint-helm: ## helm lint + kubeconform (Kubernetes 1.36 schemas)
	scripts/helm_check.sh

lint: lint-python lint-frontend lint-helm ## ruff, eslint, tsc, helm lint, kubeconform

ci: lint test test-integration build-images ## the same checks as .github/workflows/ci.yml, run locally

# ---------- local Kubernetes (k3d) ----------
K3D_CLUSTER := ea
K3S_IMAGE := rancher/k3s:v1.36.6-k3s1@sha256:88d3fac10eb4a429d3c5275f4868fe4b13620f6bbca5bdb5dca0627ac76ae2a0
CHART := deploy/helm/experiment-analyzer
.PHONY: k3d-up k3d-deploy k3d-down k3d-smoke
k3d-up: ## local k3s 1.36 cluster; API on 127.0.0.1:6550, ingress on 127.0.0.1:8081
	k3d cluster create $(K3D_CLUSTER) --image $(K3S_IMAGE) --servers 1 --agents 0 \
	  --api-port 127.0.0.1:6550 -p "127.0.0.1:8081:80@loadbalancer" --wait --timeout 180s
	kubectl config use-context k3d-$(K3D_CLUSTER)

k3d-deploy: build-images ## build images, import them into k3d, helm upgrade --install with ci/k3d-values.yaml
	k3d image import -c $(K3D_CLUSTER) experiment-analyzer-api:local experiment-analyzer-web:local
	helm upgrade --install ea $(CHART) -n experiment-analyzer --create-namespace \
	  -f $(CHART)/ci/k3d-values.yaml --wait --timeout 10m
	# The tag stays "local", so restart to pick up freshly imported images.
	kubectl -n experiment-analyzer rollout restart deploy/ea-experiment-analyzer-api deploy/ea-experiment-analyzer-worker deploy/ea-experiment-analyzer-web
	kubectl -n experiment-analyzer rollout status deploy/ea-experiment-analyzer-api deploy/ea-experiment-analyzer-worker deploy/ea-experiment-analyzer-web --timeout 5m
	kubectl -n experiment-analyzer get pods,hpa

k3d-seed: ## re-create the bucket + sample in the in-cluster moto (moto is in-memory: a moto pod restart empties it)
	kubectl -n experiment-analyzer exec deploy/ea-experiment-analyzer-api -- python manage.py seed_samples

k3d-hpa-burst: ## 20-job burst while sampling the worker HPA; writes results/hpa.json
	scripts/hpa_burst.sh experiment-analyzer 20

k3d-smoke: ## sample analysis through the k3d ingress (127.0.0.1:8081)
	python3 scripts/smoke.py http://127.0.0.1:8081 --out docs/checks/k3d_smoke.json --command "make k3d-smoke"

k3d-down:
	k3d cluster delete $(K3D_CLUSTER)

# ---------- Phase 7 helpers (need your AWS credentials; never run by Claude) ----------
.PHONY: s3-policy-check
s3-policy-check: ## real-S3 check of the presigned POST policy: make s3-policy-check S3_BUCKET=<bucket>
	cd backend && S3_BUCKET=$(S3_BUCKET) uv run python ../scripts/s3_policy_check.py

.PHONY: bullets readme
bullets: ## resume bullets with every number read from results/*.json (MISSING when absent)
	python3 scripts/bullets.py

readme: ## regenerate the README numbers table from results/
	python3 scripts/readme_numbers.py

results-tests: ## run every suite with JUnit output and write results/tests.json
	mkdir -p build
	cd abkit && uv run pytest -q --junitxml=../build/junit-abkit.xml
	cd backend && uv run pytest -q --junitxml=../build/junit-backend.xml
	JUNIT_XML=$(CURDIR)/build/junit-integration.xml scripts/integration.sh
	cd frontend && npx vitest run --reporter=default --reporter=junit --outputFile.junit=../build/junit-frontend.xml
	cd backend && uv run python ../scripts/test_counts.py ../build
