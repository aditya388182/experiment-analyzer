# CLAUDE.md: experiment-analyzer

**Project:** an A/B test analysis web app. SPEC.md is the source of truth. Work one phase at a time, and stop at each phase's Check.

## Stack (do not swap any of these; the resume names them)
| Part | Stack |
|---|---|
| Statistics | `abkit` (Python package in `abkit/`, from the lab's `abtest/stats.py`) |
| Backend | Python 3.12, Django 5.2 LTS, Django REST Framework, Celery, RabbitMQ, PostgreSQL 16, DuckDB, boto3 (S3 presigned POST) |
| Frontend | React 18.3.x (not 19), Vite, TypeScript strict, React Router, TanStack Query v5, React Hook Form + Zod, Recharts, Tailwind CSS |
| Tests | pytest + pytest-django + Hypothesis (Python); Vitest + React Testing Library + MSW (frontend) |
| Deploy | Docker (multi-stage, non-root), Kubernetes (k3s) with a Helm chart written in this repo, Traefik ingress, cert-manager TLS, GitHub Actions, images on GHCR |
| Local S3 | moto server in Docker Compose |

## Honesty of results (most important)
- Every number in the README, `results/` or the app comes from code output. Never type a result by hand.
- The lab numbers (Hillstrom 7.66 pts, CI 7.00–8.32, SRM p 0.9037, churn AUC, MASE) are reproduced or read from the copied lab JSON. They are never typed into code or tests.
- If a reproduction does not match, stop and report. Do not tweak formulas to force a match.
- `results/*.json` include the commit hash, UTC date and command. `make bullets` fills the resume bullets from them and prints MISSING for absent keys.

## Stop and ask instead of guessing
- A spec fact turns out wrong: a library API, a version incompatibility, AWS behavior, a key missing from the lab JSON.
- A step needs my AWS console, DNS, GitHub settings or secrets. Tell me exactly what to click and what values to paste.
- Any change that alters statistical results.

## Code rules
**Python:**
- type hints on public functions; ruff clean
- settings from env (django-environ or os.environ); never hard-code secrets
- DRF errors as `{"error": {"code", "message"}}`; never return tracebacks

**Celery tasks:**
- idempotent; `acks_late=True`, `reject_on_worker_lost=True`
- retry only transient errors
- soft time limit 120 s, hard 150 s

**Frontend:**
- no `any`; API types in `src/api/types.ts` match the result schema in SPEC.md section 7
- every API error is shown to the user; inputs have labels

**Docker:** multi-stage builds, non-root user, pinned base images, healthchecks.

**Helm:**
- resource requests and limits plus readiness and liveness probes on every pod
- no secrets in `values.yaml`
- `helm lint` and kubeconform clean

**Dependencies:** pin exact versions (`VERSIONS.md`, lockfiles). No Bitnami charts or images.

## Definition of done for a phase
1. Tests pass. Show the real output.
2. The phase's Check from SPEC.md has been run and its output shown.
3. Nothing left as TODO without a note in SPEC.md.
4. Committed with a message naming the phase.

## Commands
- `make dev`: Docker Compose dev stack (postgres, rabbitmq, moto, api, worker, web)
- `make test`: abkit + backend + frontend tests
- `make test-integration`: real RabbitMQ and worker end to end
- `make lint`: ruff, eslint, tsc, helm lint
- `make k3d-up` / `make k3d-deploy`: local Kubernetes test of the chart
- `make bullets`: print resume bullets from `results/`

## Working style
- Plan mode first for anything touching more than one file. One phase per session.
- Do not push, deploy or create cloud resources unless the prompt says so.
- After each phase, list anything I should understand well enough to explain in an interview.
