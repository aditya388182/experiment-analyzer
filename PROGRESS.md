# PROGRESS.md

Autonomous build log. If context is lost: re-read this file, DECISIONS.md and BLOCKERS.md, then continue with "Next".

## Toolchain (installed on the EC2 build box, 2026-11-13)

| Tool | Pinned | Installed (command output) |
|---|---|---|
| uv | 0.13.1 | `uv 0.13.1 (x86_64-unknown-linux-gnu)` |
| Python | 3.12.16 | `/home/ubuntu/.local/share/uv/python/cpython-3.12.16-linux-x86_64-gnu/bin/python3.12 --version` → `Python 3.12.16` |
| Node.js | 24.22.3 | `v24.22.3` |
| npm | 11.6.2 (VERSIONS.md) | `11.19.1` (bundled with Node 24.22.3; see DECISIONS.md D2) |
| kubectl | 1.36.x | `Client Version: v1.36.6` |
| Helm | 4.3.1 | `v4.3.1+gc0d08d0` |
| k3d | 5.9.0 | `k3d version v5.9.0` |
| kubeconform | 0.8.0 | `v0.8.0` |
| Docker | (box) | `Docker version 29.9.3, build 5457199`, `Docker Compose version v5.7.1` |

All downloads were checked against the publisher's SHA-256 checksums.

## Phases

### Phase 1: abkit — DONE
- `abkit/` package (0.1.0): lab `stats.py` ported with formulas unchanged; `power.py` (MDE, sample size, continuous MDE),
  `analysis.py` (`analyze`), `verdict.py`, `config.py`.
- Tests: equivalence (20 seeded datasets per function), Hypothesis properties, edge cases, ported lab tests, verdict
  strings, lab reproduction.
- **Check:** `make results-abkit` → `164 passed in 10.00s`.
  - `results/lab_reproduction.json`: men's vs no-email visit diff 0.07658956365153125 (7.66 pts), CI 0.06995314760976148
    to 0.083225979693301 (7.00 to 8.32), SRM p 0.9036929575604196. **abs diff to the lab = 0.0 on all 12 values checked**.
  - `results/validation.json`: max diffs: diff_in_means 2.2e-16, srm 0, holm 0, cuped 4.4e-16, MDE 2.6e-5 relative
    (vs converged statsmodels; see D5), sample size 7.1e-5 relative; 1,601 Hypothesis examples; 12 edge cases.
- Spec tolerance issue found and handled: DECISIONS.md D5 (statsmodels `solve_power` imprecision, not a formula change).

### Phase 2: Django API and uploads — DONE
- Django 5.2 project (`backend/config`), env-driven settings, Postgres, `Upload`/`Analysis` models + migration,
  presigned POST (`content-length-range` 1..50 MB, exact key), `/complete` (HEAD + 256 KB ranged GET preview),
  `/api/health`, JSON error handler, dev CORS middleware. Compose infra (`deploy/compose.dev.yml`, ports on 127.0.0.1).
- **Check:** `make test-backend` → `28 passed` (201, 413, 415, 422 ×4, 409, 422 bad CSV ×6, 404, health 200/503,
  policy conditions, ranged preview, CORS). Curl walkthrough output: `docs/checks/phase2_curl_walkthrough.txt`
  (presigned POST to moto → 204; complete → 12 columns, 20 preview rows).
- Found: moto does not enforce the POST policy → BLOCKERS.md B1 (needs a real bucket in Phase 7).
- Next: Phase 3 (Celery task, DuckDB ingest, idempotency, sample/analyses/sample-size/reports endpoints).

### Phase 3: Celery jobs — DONE
- `run_analysis` task (acks_late, reject_on_worker_lost, soft 120 s / hard 150 s, retries only transient S3 errors,
  2/4/8 s backoff), DuckDB `ingest.py` (explicit VARCHAR columns, drop counts), idempotent reuse by
  (sha256, mapping hash, abkit version), `seed_samples`, endpoints: analyses create/list/detail, sample, sample-size, reports.
- **Check:**
  - `make test-backend` → `72 passed, 5 deselected` (eager-mode unit tests: reproduction, reuse ×3, 7 bad-data codes,
    drop counts, retry/backoff, give-up, no-retry on 4xx, timeout, internal, duplicate message, redelivered RUNNING
    job, 422/404/409, 429, sample-size, reports = source JSON).
  - `make test-integration` → `5 passed` with a real RabbitMQ + worker (`docs/checks/phase3_integration.txt`):
    sample QUEUED→RUNNING→SUCCEEDED in 0.47 s, diff 0.07658956365153125, CI [0.06995314760976148, 0.083225979693301],
    SRM p 0.9036929575604196; second POST → 200 `reused_from`; re-uploaded copy reused by hash on the worker;
    bad data → FAILED `SINGLE_ARM`, attempts 1 (worker log shows one receive, no retry).
- Found and fixed: RabbitMQ 4.3 refuses Celery's transient control queues (D9); DuckDB sniffer mis-reading ragged files (D10).
- Next: Phase 4 (React frontend).

### Phase 4: React frontend — DONE
- Vite 8 + React 18.3.1 + TS 6 strict + Tailwind 4, react-router 7, TanStack Query 5 (1 s polling until terminal),
  RHF + Zod mapping and sample-size forms, Recharts forest plot / MASE bars / MDE curve. Six pages: Home, Upload, Analysis,
  Sample size, Model reports, Method.
- **Check:**
  - `make test-frontend` → `32 passed` (mapping validation ×7, polling stops at terminal, verdict / SRM banner (green and red)
    / CUPED card (helpful and not), failure panel, 404 message, upload progress via mocked XHR, S3 rejection, 415 message,
    429 message, sample size, reports, method, fixture keys = TS types). Stable over 4 consecutive runs.
  - `make lint-frontend` → tsc clean, eslint 0 errors 0 warnings. `npm run build` OK.
  - Screenshots of every page against the dev stack (real sample runs, a real 3.9 MB upload with the progress bar at 31%,
    a queued state with the worker stopped, a real failure): `docs/screenshots/01..11-*.png`.
  - Backend after the Phase 4 fix: `73 passed, 5 deselected`.
- Found and fixed via the screenshot run: metric-type guess on an all-zero preview (D11).
- Next: Phase 5 (Dockerfiles, compose with all services, make dev/test, ci.yml).

### Phase 5: Docker and CI — DONE (except the GitHub run link: BLOCKERS.md B2)
- `deploy/docker/api.Dockerfile` (api + worker, multi-stage, uv, uid 10001), `web.Dockerfile` (node build → nginx-unprivileged,
  uid 101), `nginx.conf` / `nginx.dev.conf`, digest-pinned base images, healthchecks. `deploy/compose.dev.yml` with all
  services (postgres, rabbitmq, moto, migrate, api, worker, web), all on 127.0.0.1. `make dev`, `make test`, `make lint`,
  `make ci`, `make results-tests`. `.github/workflows/ci.yml` (7 jobs, actions pinned by SHA).
- **Check (local equivalent of CI; a GitHub run needs a push → B2):**
  - `make dev` → all 7 services healthy; api/worker run as uid 10001, web as uid 101; SPA fallback 200, missing
    asset 404; sample analysis through nginx → SUCCEEDED, 7.66 pts verdict.
  - `make lint-python lint-frontend` → ruff clean (abkit, backend), tsc clean, eslint 0 warnings.
  - `make results-tests` → abkit 164, backend 73, integration 5, frontend 32: **274 passed, 0 failed**
    (`results/tests.json`).
  - `make build-images` → api 732 MB, web 91 MB.
  - ci.yml parses; all `uses:` pinned to 40-char SHAs.
- Next: Phase 6 (Helm chart, k3d install, ingress sample analysis, HPA).

### Phase 6: Helm chart and local Kubernetes — DONE
- Chart `deploy/helm/experiment-analyzer` (apiVersion v2, Helm 4): api / worker / web Deployments, postgres + rabbitmq
  StatefulSets with PVCs (local-path), Services, Traefik Ingress with cert-manager annotation, worker HPA (1–3, CPU 70%),
  migrate + seed Job as a `post-install,pre-upgrade` hook (D13), ConfigMap, Secret (generated only for local clusters),
  probes and requests/limits on every long-running pod, non-root and read-only root filesystems, no SA token.
  `ci/k3d-values.yaml` adds an in-cluster moto. `make k3d-up / k3d-deploy / k3d-smoke`.
- Phase 7 files drafted (not run, need AWS/DNS/GitHub): `deploy/aws/*`, `deploy/box/bootstrap.sh`,
  `deploy/box/remote-deploy.sh`, `.github/workflows/deploy.yml`, `scripts/smoke.py`, `scripts/s3_policy_check.py`.
  Steps for the owner: BLOCKERS.md B3–B7.
- **Check** (`docs/checks/phase6_k3d.txt`):
  - `scripts/helm_check.sh` → helm lint clean; kubeconform 15/15 (production values) and 18/18 (k3d values) valid
    against Kubernetes 1.36.0; ConfigMap integers OK.
  - Fresh `helm install` on k3d (k3s v1.36.6+k3s1) → `STATUS: deployed`; the post-install migrate Job "Job completed";
    `kubectl get pods`: all 6 pods 1/1 Running, 0 restarts.
  - Sample analysis through the Traefik ingress (127.0.0.1:8081) → POST 202, QUEUED → SUCCEEDED in 0.57 s, verdict
    "Mens E-Mail increased visit rate by 7.66 percentage points (95% CI 7.00 to 8.32) …".
  - `kubectl get hpa` → worker HPA 1–3 replicas at 70% CPU (HPA burst result: see results/hpa.json).
  - `helm upgrade` (revision 2) ran the pre-upgrade migrate hook successfully.
- Found and fixed on k3d: Helm float rendering of 52428800 (D13), pre-upgrade hook reading the old ConfigMap (D13).
  Found while writing the IAM policy: S3 403 for missing keys without ListBucket (D14), fixed + 2 tests (backend 75 passed).
- Next: Phase 8 (README evidence pack, `make bullets`, final review against Done means, DONE.md).

### Phase 8: evidence and finish — DONE (deploy numbers wait for Phase 7)
- README evidence pack: pitch, CI badge, GIF of a real sample run (`docs/sample-run.gif`, recorded on k3d), Mermaid
  architecture diagram, numbers table generated from `results/` (`make readme`), how to run, testing approach, design
  decisions, limits. `make bullets` (`scripts/bullets.py`). DONE.md with every results value generated by
  `scripts/done_results.py`.
- HPA burst on k3d (`scripts/hpa_burst.sh`): 20 distinct 800k-row jobs, worker CPU 382% of request, replicas 1 → 3,
  20/20 SUCCEEDED (`results/hpa.json`, labelled k3d). The first rerun reused identical files by hash (no load), so each
  run now uses a fresh seed.
- All results regenerated on a clean commit (`dirty: false`). The results metadata's dirty check had a bug (stripping
  the first porcelain line) and was fixed.
- **Check:** `make bullets` → three bullets; the only MISSING is `results/deploy_smoke.json` (Phase 7, B7).
  277 tests passed, 0 failed (after review fixes). Subagent review against SPEC §14: 7 gaps found and fixed; see DONE.md section 6.

## Next
Phase 7 is yours: BLOCKERS.md B3 → B4 → B5 → B6 → B7 → B1 → B2 → B8 (summary in DONE.md section 4).
