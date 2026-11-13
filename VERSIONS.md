# VERSIONS.md

Exact pins for every runtime, library, image and tool. Lockfiles (`uv.lock`, `package-lock.json`) pin the transitive dependencies. This file pins the direct ones and records why.

**Researched:** 2026-11-13, from PyPI, the npm registry, Docker Hub and GitHub releases.
**Rule used:** the newest release that is at least ~2 weeks old (published on or before 2026-10-30), unless a constraint below says otherwise. Very new majors or minors (days old) are skipped on purpose and noted.

Fixed by decision (do not change): Python 3.12, Django 5.2 LTS, React 18.3.1, Helm 4, an LTS Node.

---

## Runtimes

| Item | Pin | Released | Notes |
|---|---|---|---|
| Python | **3.12.16** | image 2026-11 | 3.12 receives security fixes only (until 2028-10). numpy 2.5 and scipy 1.18 need >= 3.12, so 3.12 is the floor as well as the target. `requires-python = "==3.12.*"`. |
| Node.js | **24.22.3** (LTS "Krypton") | 2026-11-10 | LTS until 2028-04. Node 26 became Active LTS in 2026-10, but 24 has a year of LTS behind it and every tool below supports it. Committed as `.nvmrc`. |
| npm | **11.19.1** | — | bundled with Node 24.22.3; set in `packageManager` (was 11.6.2 from the laptop; DECISIONS.md D2) |
| uv (Python env + lock) | **0.13.1** | 2026-10 | produces `uv.lock` for `abkit/` and `backend/` |

## Python: backend (`backend/pyproject.toml`)

| Package | Pin | Released | Notes |
|---|---|---|---|
| Django | **5.2.19** | 2026-11-03 | latest 5.2 LTS patch (LTS until 2028-04). 6.1.3 exists and is deliberately not used. |
| djangorestframework | **3.18.3** | 2026-10-06 | classifiers list Django 5.2, 6.0, 6.1 and Python 3.12 |
| django-environ | **0.14.0** | 2026-06-18 | lists Django 5.2 |
| psycopg[binary] | **3.3.6** | 2026-09-18 | 3.3.7, 3.3.8 and 3.3.9 came out in the last 10 days, so this skips them |
| celery | **5.6.3** | 2026-03-26 | 5.7.0 came out 2026-11-05 (8 days ago), so this skips it |
| kombu | **5.6.2** | 2025-12-29 | pinned explicitly so the resolver does not pull 5.7.x (the line that pairs with Celery 5.7) |
| amqp | **5.4.1** | 2026-10-05 | py-amqp transport for RabbitMQ |
| boto3 | **1.43.123** | 2026-10-30 | `generate_presigned_post`; releases daily, so a ~2-week-old pin is fine |
| duckdb | **1.5.6** | 2026-09-28 | **2.0.0** (2026-10-21) is a new major. See concern 3. |
| numpy | **2.5.4** | 2026-10-10 | |
| gunicorn | **26.2.0** | 2026-08-24 | 27.0.0 is a new major from 2026-11-10, so this skips it |

## Python: `abkit/` (`abkit/pyproject.toml`)

| Package | Pin | Released | Notes |
|---|---|---|---|
| numpy | **2.5.4** | 2026-10-10 | runtime dependency |
| scipy | **1.18.1** | 2026-08-21 | runtime (t and chi-square distributions); also the equivalence reference |
| statsmodels | **0.15.0** | 2026-08-27 | **test-only** (`multipletests`, `NormalIndPower`, OLS references) |
| pandas | **3.0.6** | 2026-09-17 | test-only, pulled in by statsmodels. 3.1.x is newer than statsmodels 0.15.0, so this stays on 3.0. |

## Python: tests and lint (dev group, both packages)

| Package | Pin | Released |
|---|---|---|
| pytest | **9.2.0** | 2026-10-27 |
| pytest-django | **4.14.0** | 2026-08-10 (lists Django 5.2) |
| pytest-cov | **7.1.0** | 2026-03-21 |
| hypothesis | **6.170.14** | 2026-10-30 |
| moto[server,s3] | **5.2.5** | 2026-10-27 (matches the Compose image) |
| ruff | **0.17.3** | 2026-10-27 |
| hatchling (build backend) | **1.33.0** | 2026-10-28 |

## Frontend (`frontend/package.json`, exact versions, no `^`)

| Package | Pin | Released | Notes |
|---|---|---|---|
| react / react-dom | **18.3.1** | 2024 | last 18.x; 19.3.1 is latest and is not used |
| @types/react | **18.3.31** | 2026-06-05 | must stay on 18.x to match React 18 |
| @types/react-dom | **18.3.7** | — | |
| react-router | **7.18.5** | 2026-10-27 | **v8 requires React >= 19.2.7**, so the pin stays on 7.x. See concern 1. |
| @tanstack/react-query | **5.105.0** | ≤ 2026-10-30 | peer `react ^18 \|\| ^19` |
| react-hook-form | **7.91.0** | ≤ 2026-10-30 | |
| zod | **4.6.7** | 2026-10-12 | |
| @hookform/resolvers | **6.0.2** | 2026-10-28 | peer `zod ^3.25 \|\| ^4`, `react-hook-form ^7.55`. 7.0 is 2 days old, so this skips it. |
| recharts | **3.10.1** | 2026-07-25 | peer includes React 18 |
| tailwindcss | **4.3.3** | ≤ 2026-10-30 | v4: configured in CSS, no `tailwind.config.js` |
| @tailwindcss/vite | **4.3.3** | ≤ 2026-10-30 | peer `vite ^5.2 \|\| ^6 \|\| ^7 \|\| ^8` |
| vite | **8.3.5** | ≤ 2026-10-30 | node `^20.19 \|\| >=22.12` |
| @vitejs/plugin-react | **6.1.2** | 2026-10-05 | peer `vite ^8` |
| typescript | **6.0.3** | 2026-04-16 | **not 7.x.** See concern 2. |
| vitest | **5.0.5** | ≤ 2026-10-30 | node `^22.12 \|\| ^24 \|\| >=26` |
| jsdom | **30.1.3** | ≤ 2026-10-30 | 31.0 was released today |
| @testing-library/react | **16.3.3** | 2026-08-27 | peer React 18 or 19 |
| @testing-library/dom | **10.4.2** | 2026-09-13 | required peer of RTL 16 |
| @testing-library/jest-dom | **7.0.1** | 2026-08-09 | |
| @testing-library/user-event | **14.6.8** | ≤ 2026-10-30 | |
| msw | **3.0.3** | ≤ 2026-10-30 | node >= 22.12, peer TS >= 5.9 |
| eslint | **10.14.0** | 2026-10-30 | flat config |
| @eslint/js | **10.0.1** | 2026-02-06 | |
| typescript-eslint | **8.72.1** | ≤ 2026-10-30 | peer `typescript >=4.8.4 <6.1.0` |
| eslint-plugin-react-hooks | **7.1.1** | 2026-04-17 | |
| eslint-plugin-react-refresh | **0.5.7** | 2026-09-14 | |
| globals | **17.13.0** | 2026-10-01 | |
| @types/node | **24.19.2** | 2026-10-09 | matches Node 24 |

## Container images (pinned by tag now; digests added in Phase 5)

| Image | Tag | Use |
|---|---|---|
| python | **3.12.16-slim-trixie** | api and worker build and runtime stages (Debian 13) |
| node | **24.22.3-alpine3.24** | frontend build stage only |
| nginxinc/nginx-unprivileged | **1.30.6-alpine** | web runtime. 1.30 is nginx's stable branch, and the image runs as non-root on port 8080. Official NGINX image, not Bitnami. |
| postgres | **16.16-trixie** | Compose and StatefulSet. Debian (glibc) rather than Alpine (musl) keeps text sort order (collation) consistent. 16.16 was published 2026-11-12, a quarterly patch release. |
| rabbitmq | **4.3.7-management-alpine** | Compose and StatefulSet. 4.4.0 (2026-10-19) is a new minor, so this skips it. |
| motoserver/moto | **5.2.5** | local S3 in Compose and CI |
| rancher/k3s | **v1.36.6-k3s1** | k3d local cluster (same as the box) |

## Kubernetes and deploy tooling

| Tool | Pin | Notes |
|---|---|---|
| k3s (EC2 box) | **v1.36.6+k3s1** (2026-11-03) | One minor behind the newest k3s (1.37), because cert-manager 1.21 supports Kubernetes 1.33–1.36 only. |
| Traefik | **v3.7.15** (bundled with k3s 1.36.6) | not installed separately. Pinned by the k3s version. |
| cert-manager | **v1.21.3** (2026-10-23) | supports Kubernetes 1.33–1.36; includes the eMudhra CA trust removal |
| Helm | **v4.3.1** (2026-10-15) | Decision: Helm 4. The chart uses `apiVersion: v2`, which Helm 4 still supports. |
| kubectl | **v1.36.x** | must be within one minor of the server (see concern 6) |
| k3d | **v5.9.0** (2026-06-02) | run with `--image rancher/k3s:v1.36.6-k3s1` |
| kubeconform | **v0.8.0** (2026-06-04) | validate against Kubernetes 1.36.0 schemas |
| AWS CLI | **2.x** (local 2.38.1) | only used by `deploy/aws/s3-setup.sh` |

GitHub Actions versions are pinned by commit SHA in Phase 5.

---

## Compatibility concerns

1. **React 18 means the frontend stays on older major versions.** react-router 8 needs React >= 19.2.7, so the pin is react-router 7.18.5. In v7, `react-router` is the main package and `react-router-dom` is only a re-export, so we use `react-router` alone. `@types/react` and `@types/react-dom` must also stay on 18.x, or the type checker reports false errors. Every other UI library here (TanStack Query, RHF, Recharts, RTL) still declares React 18 as a supported peer. In later upgrades, check each library's peer dependencies before bumping it.
2. **TypeScript 7 is not usable yet.** TypeScript 7.0 (the native Go port, 2026-07) is the npm `latest`, but `typescript-eslint` 8.72 requires `typescript <6.1.0`. Pin 6.0.3. `msw` 3 needs TS >= 5.9, which 6.0.3 satisfies.
3. **DuckDB 2.0 is skipped.** It is a new major (3 weeks old). We only use `read_csv` with explicit types, `TRY_CAST`, `GROUP BY` and `fetchnumpy()`, which 1.5.6 covers. Moving to 2.0 later is a separate change with its own test run, not part of Phase 3.
4. **Celery 5.6 with RabbitMQ 4.x.** It works over AMQP 0-9-1 with py-amqp. Two points:
   - RabbitMQ 4 removed classic mirrored queues and deprecates transient non-exclusive queues. Celery's default durable classic `celery` queue is fine. **Correction (Phase 3):** Celery's remote-control (pidbox) and gossip/mingle queues are transient non-exclusive and RabbitMQ 4.3 refuses them by default. Fixed with `control_queue_exclusive` / `event_queue_exclusive` = True (DECISIONS.md D9).
   - Quorum queues do not support the global QoS (prefetch) setting. We stay on classic queues and set `worker_prefetch_multiplier=1` with `acks_late=True`. Switching to quorum queues is future work, not needed here.
   - Keep `kombu` pinned to 5.6.2. Celery 5.6.3 only says `kombu>=5.6.0`, so without the pin the resolver would pull kombu 5.7.
5. **statsmodels 0.15.0 is the slowest-moving package here.** It is used only in tests. pandas stays on 3.0.6 (released after statsmodels 0.15.0, but the same minor line) instead of 3.1.x, which came out after statsmodels. If the equivalence tests show deprecation noise from scipy 1.18, that is a warning, not a failure, and is recorded rather than suppressed.
6. **Your machine differs from these pins.** Nothing in the repo depends on these, but they will bite in later phases:
   - **Node v25.2.1 is installed.** That is an odd-numbered release that is no longer supported, not an LTS. Install 24.22.3 (`fnm install 24.22.3` or `nvm install 24.22.3`), and `.nvmrc` will select it.
   - **System Python 3.12.3.** Use `uv python install 3.12.16` so local tests match the image.
   - **kubectl 1.34.1** is two minors behind k3s 1.36. Kubernetes supports only ±1 minor between client and server, so upgrade it to 1.36.x before Phase 6.
   - **Helm and k3d are not installed.** You need them for Phase 5 (`helm lint`) and Phase 6.
7. **cert-manager limits the k3s version.** cert-manager 1.21 supports Kubernetes 1.33–1.36. Do not move the box to k3s 1.37 until a cert-manager release that supports 1.37 (1.22, expected ~2026-11) is out and pinned here.
8. **moto and presigned POST (Phase 2 risk, not a version problem).** SPEC.md section 12 already says that if moto does not enforce the POST policy (for example `content-length-range`) the way AWS does, we use a real dev bucket instead. The Phase 2 test checks this explicitly rather than assuming it.
9. **Postgres 16.16 is one day old.** It is a patch release (usually security fixes), so it is pinned anyway. If its release notes require a reindex or a manual step, fall back to 16.15.
