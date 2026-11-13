# DECISIONS.md

Choices made while building without the owner available. Each one: what, why, and how to undo it.

## D1. Python 3.12.16 installed from the python-build-standalone release by hand
`uv python install 3.12.16` fails on uv 0.13.1 ("No download found"): uv's built-in download list predates the
`20261110` python-build-standalone release that contains 3.12.16. Rather than move off the pinned uv, I downloaded
`cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`, checked it against the release's
`SHA256SUMS`, and unpacked it to `~/.local/share/uv/python/cpython-3.12.16-linux-x86_64-gnu/`, where uv finds it as a
managed interpreter (`uv python find 3.12.16` works). A newer uv would do this itself.

## D2. npm 11.19.1 (bundled with Node 24.22.3) instead of 11.6.2
VERSIONS.md lists npm 11.6.2 as "ships with the dev machine" (the laptop's Node 25). Node 24.22.3 bundles npm 11.19.1.
Downgrading npm below what the pinned Node ships with has no benefit, so `packageManager` is `npm@11.19.1` and
VERSIONS.md is updated.

## D3. Git author for commits on this box
The box had no git identity. I set a repo-local identity equal to the author of the existing commits
(`git config user.name/user.email` in `.git/config` only), so history stays consistent.

## D4. abkit: which lab code moves over
All of `abtest/stats.py` moves into `abkit/stats.py` with formulas unchanged (`srm_test`, `diff_in_means`,
`bootstrap_diff_ci`, `holm`, `cuped`, `regression_adjusted_effect`, `aa_false_positive_rate`); `mde_two_proportions`
moves to `abkit/power.py`. `uplift.py` and `sequential.py` stay in the lab (uplift models are out of scope, SPEC section 2).
The lab tests for those functions are ported; tests that import the lab's `run.py`, `uplift.py` or scikit-learn are not.
`cuped` gained a separate `cuped_theta(y, x)` helper; `cuped` calls it, and the expression is the same one the lab used.

## D5. MDE / sample-size equivalence: what "statsmodels" means at 1e-4 (a spec tolerance that did not hold as written)
SPEC section 8 says to check `mde_two_proportions` against `NormalIndPower().solve_power(...) x sqrt(p(1-p))` at
1e-4 relative. On 2 of 20 seeds that fails (1.24e-4 and 1.32e-4). The cause is statsmodels' root-finder, not our
formula: at statsmodels' own returned effect size, statsmodels' own power function gives 0.79990 instead of the requested
0.8. At *our* MDE, statsmodels' power function gives exactly target + far-tail (to 1e-9). The abkit formula was not
touched. The test now checks three things:
1. statsmodels `power()` at our MDE equals target power plus the far-tail term (1e-9 absolute);
2. our MDE vs statsmodels' MDE solved to full precision (brentq, xtol 1e-15) on statsmodels' power curve: 1e-4 relative (the spec's tolerance);
3. our MDE vs raw `solve_power` output: 1e-3 relative (recorded separately in validation.json).

For `sample_size_two_proportions` the spec's "round trip within 1 unit" holds exactly. The extra comparison with
statsmodels' smallest n differs by 2 at n = 817,099 (relative 2.4e-6) because statsmodels counts the far tail, so that
comparison uses max(1 unit, 1e-5 relative).

## D6. CUPED: pooled across all arms, with the lab's per-pair view alongside
`result.cuped.corr` / `variance_removed` / `theta` are computed on all arms pooled, and one theta adjusts every arm, which is the usual
multi-arm CUPED. The lab measured CUPED per treatment-vs-control pair (men's + no-email rows: corr 0.0667,
variance removed 0.44%). The result also carries `cuped.by_comparison` with that per-pair view, and the lab-reproduction
test checks it against the lab JSON. On Hillstrom the pooled corr is 0.065 and the per-pair corr is 0.067. Both are "not helpful".

## D7. Result schema additions (SPEC section 7 shows the shape; these fields are added, nothing removed)
- top level: `metric_col`, `metric_type`, `control_label`, `alpha` (the verdict template needs them)
- comparisons: `treat_mean`, `ctrl_mean`, `se`, `degenerate`; `rel_lift` is `null` when the control mean is 0
- srm: `observed_split`
- power: `sd` (control SD; used for continuous MDE), `base_rate` is `null` for continuous metrics, `mde_abs` is `null` when undefined (base rate 0 or 1, or zero SD)
- cuped: `pre_period_col`, `theta`, `by_comparison`
- rows.dropped: adds `null_pre_period` (SPEC section 8 edge case: missing pre-period rows are dropped and counted)
- `power.n_per_arm` is the smallest arm (conservative); on Hillstrom that is the control arm, as in the lab.
- `planned_split` order: the control first, then the other arms in ascending label order (the order arms appear in the result). A length mismatch fails with `PLANNED_SPLIT_MISMATCH`.
- Extra error codes: `PLANNED_SPLIT_MISMATCH`, `BAD_PLANNED_SPLIT`.
- Validation order: SINGLE_ARM, CONTROL_NOT_FOUND, TOO_MANY_ARMS, ARM_TOO_SMALL, CONSTANT_METRIC. ARM_TOO_SMALL is checked before CONSTANT_METRIC because a 1-row arm has no variance.
- When both arms of a comparison have zero variance (but others do not), the comparison is reported as degenerate (CI = point, p = 0 or 1) with a warning, instead of dividing by zero.

## D8. Phase 2 details
- **Validation status code:** all request-validation failures return 422 (`VALIDATION_ERROR`), matching the 422s in
  SPEC section 6. Malformed JSON is 400 `BAD_JSON`.
- **Error codes:** 413 `FILE_TOO_LARGE`, 415 `UNSUPPORTED_FILE_TYPE`, 409 `OBJECT_MISSING`, 422 `BAD_CSV`, 404 `NOT_FOUND`,
  429 `RATE_LIMITED`, 500 `INTERNAL` (no traceback; logged server-side).
- **Preview:** a ranged GET of the first 256 KB; when the object is longer, the partial last line (which can split a
  UTF-8 character) is dropped before decoding. UTF-8 with or without BOM is accepted. 422 for non-UTF-8, NUL bytes,
  fewer than 2 columns, duplicate header names, ragged rows or no data rows.
- **Oversize objects:** moto ignores the POST policy (BLOCKERS.md B1), so `/complete` also checks the HEAD size and
  returns 413. The object is left in place: the IAM policy has no DeleteObject, and the 7-day lifecycle rule removes it.
- **CORS:** a 20-line middleware (`analyzer/middleware.py`) instead of adding django-cors-headers, which is not pinned in
  VERSIONS.md. It is only needed in dev (Vite on 5173 calling the API on 8000). In the cluster the SPA and the API share one origin.
- **Throttle storage:** DRF throttling uses Django's cache. LocMemCache would be per gunicorn process, so the 30/hour
  limit uses `DatabaseCache` in Postgres (`createcachetable` runs with migrations).
- **The `api` Compose service comes in Phase 5**, when the Dockerfiles are written, so the image is written once. In
  Phase 2 the API ran on the host (gunicorn) against the Compose postgres, rabbitmq and moto (`make run-api`).
- **Ports:** every Compose port is published on 127.0.0.1 only (owner's instruction). On the EC2 box, use an SSH tunnel.
- **Health:** `/api/health` checks the DB (`SELECT 1`) and the broker (AMQP connect, 2 s timeout) and returns 503 if either fails.

## D9. RabbitMQ 4.3 and Celery's transient queues (VERSIONS.md concern 4 was wrong)
VERSIONS.md said Celery's remote-control queues are "still allowed by default in 4.3". They are not: the worker
crashed in a restart loop with `Queue.declare: (541) INTERNAL_ERROR - Feature transient_nonexcl_queues is deprecated`.
Celery declares transient, non-exclusive queues for remote control (pidbox) and gossip/mingle events.
Fix, without re-enabling a deprecated RabbitMQ feature: `CELERY_CONTROL_QUEUE_EXCLUSIVE = True` and
`CELERY_EVENT_QUEUE_EXCLUSIVE = True` (both options exist in Celery 5.6). Verified: the worker starts and
`celery inspect ping` gets `pong`. The task queue itself stays the durable classic `celery` queue. VERSIONS.md concern 4 is corrected.

## D10. Phase 3 details
- **Reuse must also match abkit_version.** The idempotency key is sha256(file) + sha256(canonical mapping) as specified,
  and reuse additionally requires the same `abkit_version`, so a stats fix in a new abkit release is never hidden by
  an old stored result.
- **Immediate reuse at POST.** When the same stored object (same upload id, or the same sample) already has a
  SUCCEEDED analysis with the same mapping, the API creates a new SUCCEEDED row with `reused_from` set and returns 200.
  A new row, rather than the old id, keeps "every POST gets its own shareable link that says where it came from".
  Different uploads of identical bytes are matched by hash in the worker. `reused_from` always points at the
  original computation (never at another reuse).
- **DuckDB reads with explicit types and the sniffer off.** A ragged row late in a file made DuckDB's auto-detect
  silently take that row as the header. Now the header is parsed with Python's `csv`, every column is declared
  VARCHAR, `auto_detect = false`, `strict_mode = true`, so a ragged row fails with `BAD_CSV` and the line number.
- **Extra error codes:** `NO_USABLE_ROWS` (every row dropped; message lists the reasons), `BAD_CSV`,
  `MAPPING_COLUMN_MISSING`, `OBJECT_MISSING`, `UPLOAD_GONE`, `STORAGE_UNAVAILABLE` (3 retries exhausted), `TIMEOUT`
  (soft limit), `INTERNAL`.
- **Transient = network errors and S3 SlowDown/5xx/RequestTimeout.** AccessDenied and other 4xx are not retried
  (they become INTERNAL and are logged). Backoff is 2, 4 and 8 s.
- **`attempts`** (extra model field, shown in the API) counts task runs, so "not retried" is visible: bad data shows `attempts: 1`.
- **Eager-mode tests drive retries by hand.** Celery eager mode raises `Retry` rather than re-running the task, so
  the unit test calls `apply(retries=k)` for each redelivery and checks the backoff (2 s, 4 s). The real broker path
  is covered by `make test-integration`.
- **Integration test runs against a fresh `analyzer_it` database** (dropped and recreated by the script inside the
  Compose Postgres), so reuse state from earlier runs cannot hide real work. The API runs on 127.0.0.1:8001.
- **Liveness vs readiness:** `/api/health/live` (no dependency checks) for liveness probes; `/api/health` (DB +
  broker) for readiness. A broker outage then takes the pod out of the Service without restarting it.
- **Reports:** the cards return a `sources` map (output key → `file:key.path`), and the test checks every number in the
  response against its source, 40+ values.

## D11. Phase 4 (frontend) details
- **Same-origin API in dev.** Vite proxies `/api` to the Django API, so the SPA calls relative `/api/...` exactly as it
  does behind nginx and Traefik in the cluster. `VITE_API_BASE_URL` defaults to "" (tests set it to http://localhost
  for MSW). The CORS middleware stays for anyone who points Vite at another API origin.
- **react-router 7 as `react-router`** (VERSIONS.md concern 1); `createBrowserRouter` data router.
- **MSW 3 renamed `onUnhandledRequest` to `onUnhandledFrame`.** The old key was silently ignored (unhandled requests only
  warned); tests now use `onUnhandledFrame: "error"`.
- **Upload progress test is step-driven.** A fake XHR emits progress only when the test tells it to; the first,
  timer-based version flaked under full-suite CPU load.
- **Fixtures are real API responses** captured from the dev stack (`frontend/tests/fixtures/*.json`), and a test checks
  their keys match `src/api/types.ts`, so the Python result schema and the TS types cannot drift silently.
- **Metric-type suggestion fixed after the screenshot run found a bug.** The form guessed "binary" for `spend` because
  the 20 preview rows were all 0. The job then dropped every non-0/1 row and failed with CONSTANT_METRIC. Now
  the form only suggests binary when both 0 and 1 appear, and the worker's error message names the dropped rows
  ("... rows were dropped because the metric was not 0/1. Is the metric type right?").
- **Screenshots** are taken by `scripts/screenshots.mjs` with Playwright 1.64.1 (released 2026-10-14) installed
  outside the repo, not a project dependency. `npx playwright install-deps chromium` installed Chromium's system
  libraries with apt on the build box. For the "queued" shot the worker is really stopped and restarted, and the upload
  shot throttles upload bandwidth (CDP) so a real 3.9 MB upload to moto shows the bar mid-way.
- **Bundle size:** 849 kB JS (253 kB gzip), mostly Recharts. Route-level code splitting is possible future work.

## D12. Phase 5 (Docker and CI) details
- **One backend image, two commands.** `api.Dockerfile` builds a uv-locked venv in a build stage and copies only
  `/opt/venv` and `backend/` into a slim runtime with uid 10001. The worker uses the same image with a `celery` command.
  Size: 732 MB uncompressed, of which the venv is 423 MB (scipy 109, duckdb 58, django 50, numpy 43, botocore 31 MB).
  These are real runtime dependencies, so nothing was trimmed.
- **Base images are pinned by digest** (multi-arch index digests resolved on 2026-11-13), as VERSIONS.md planned for Phase 5.
- **nginx:** `nginx.conf` (in the image) serves the SPA with an index.html fallback and immutable `/assets/`.
  `nginx.dev.conf` is mounted only by Compose and adds the `/api` proxy, which matches "proxy /api in dev only".
- **Compose migrations** run in a one-shot `migrate` service (migrate, createcachetable, seed_samples). api and worker
  start only after it exits 0, the same pattern as the Helm pre-install hook Job in Phase 6.
- **Healthchecks:** api → `/api/health/live`; worker → `celery inspect ping` (needs D9's exclusive control queue);
  web → `/healthz`; postgres, rabbitmq and moto have their own.
- **Python 3.12.16 in CI** uses `scripts/install_python.sh` (D1 made repeatable: download the pinned standalone
  build and check a SHA-256 written into the script). The script keeps the tarball in `~/.cache` rather than deleting
  temp files, following the owner's no-`rm` rule.
- **Integration runs on its own Celery queue** (`CELERY_QUEUE=integration-<pid>`), so a dev worker on the same broker
  cannot take its jobs. Found when running integration with the Compose stack up.
- **results/tests.json** comes from JUnit XML written by every suite (`make results-tests`, `scripts/test_counts.py`).
- **Frontend test teardown order:** unmount, then reset MSW handlers. The other order let a still-polling page fire
  one unhandled request (a rare race, seen once in about 10 runs).

## D13. Phase 6 (Helm chart) details
- **Migration hook is `post-install,pre-upgrade`, not `pre-install,pre-upgrade`.** SPEC says pre-install, but Postgres
  is a StatefulSet in the same chart, and Helm runs pre-install hooks before it creates any regular resource. A
  pre-install migration would wait for a database that does not exist yet. On upgrades the hook still runs *before* the
  new api/worker pods (pre-upgrade). On the first install the API answers health checks before migrating but has no
  tables for a few seconds. An initContainer in the Job waits for Postgres's TCP port.
- **The migrate Job has its own hook ConfigMap.** Found on k3d: pre-upgrade hooks run before Helm updates regular
  resources, so a Job reading the main ConfigMap got the *old* settings and crashed. Both ConfigMaps render from one
  template (`ea.configData`), so they cannot differ.
- **Numbers in values.yaml go through `int64`.** Found on k3d: Helm parses 52428800 as a float and `quote` rendered
  "5.24288e+07", which crashed Django's int parsing. kubeconform cannot see this (it is a valid string), so
  `scripts/helm_check.sh` also checks the rendered ConfigMap holds plain integers.
- **Secrets:** none in values.yaml. Production references `secrets.existingSecret` (created by deploy.yml from GitHub
  secrets). Local clusters use `secrets.create=true`: random values generated in-cluster, kept across upgrades by
  `lookup`, and annotated `helm.sh/resource-policy: keep` so a reinstall still matches the database on the PVC.
  `DATABASE_URL` and `CELERY_BROKER_URL` are built in the pod spec with `$(POSTGRES_PASSWORD)` expansion.
- **Probes:** api readiness `/api/health` (DB + broker), liveness `/api/health/live` (process only), so a broker outage
  takes the API out of the Service without restarts. Probes send `Host: localhost` (in DJANGO_ALLOWED_HOSTS), because
  the kubelet's default Host is the pod IP. Worker readiness = broker TCP reachable; liveness = `celery inspect ping`
  every 60 s. Postgres: `pg_isready`. RabbitMQ: `check_port_connectivity` / `ping`. Web: `/healthz`. The migrate Job
  pod has no probes: probes do not apply to run-to-completion Job pods, so `backoffLimit` and `activeDeadlineSeconds`
  bound it instead.
- **Hardening:** every pod runs non-root with seccomp RuntimeDefault, no privilege escalation, all capabilities dropped,
  and a read-only root filesystem with an emptyDir `/tmp`. RabbitMQ is the exception: it writes generated config under
  /etc. The ServiceAccount does not mount a token. The worker gets `terminationGracePeriodSeconds: 160`, longer than
  the 150 s hard limit, so a scale-down lets a running job finish.
- **Ingress:** one Ingress, `/api` → api:8000 and `/` → web:8080, class traefik, cert-manager annotation when TLS is on.
  No forced HTTP→HTTPS redirect yet: a global Traefik redirect can interfere with the HTTP-01 challenge on the first
  issuance. It can be added after the certificate exists (BLOCKERS.md B7).
- **k3d:** `devS3.enabled` adds an in-cluster moto (local only). Browser uploads are not reachable from the host in
  k3d because presigned URLs point at the in-cluster moto Service. The Check uses the sample analysis, which needs no browser upload.
- **The k3d API server and ingress are bound to 127.0.0.1** (owner's instruction to keep ports local).

## D14. S3 answers 403 for missing keys under the production IAM policy
Found while writing `deploy/aws/iam-policy.json`. SPEC section 12 grants only PutObject/GetObject (HeadObject is covered by
GetObject) on `uploads/*` and `samples/*`, with no `s3:ListBucket`. Without ListBucket, S3 returns **403**, not 404, for a
key that does not exist. moto always says 404, so the tests could not show it. Before the fix, production would have
answered `/complete` with 500 instead of 409, crashed `seed_samples` on the first deploy, and called an expired upload
INTERNAL. Now `storage.is_missing()` treats 403/AccessDenied like 404 for HEAD and GET, logs it, and the tests cover
both. The cost: a real permission misconfiguration also reads as "missing". The alternative was adding s3:ListBucket on
the bucket, which widens the role, so I kept the narrower policy.
