# Experiment Analyzer: A-to-Z Build Guide

**Project 1 of 5 to build** (P3 in the master plan): a DS project with a full software stack.

**How to use this file:** copy it into the new repo as `SPEC.md`, and put `CLAUDE.md` (from the same folder) at the repo root. Then follow section 13 one phase at a time with Claude Code.

---

## 1. What you are building

**One-line pitch:** a web app where anyone uploads an A/B test results file (or clicks one button to use a real 64,000-customer email test) and gets back a correct, plain-English readout:
- did the change win, and by how much (with a 95% CI)
- was the traffic split healthy (sample ratio mismatch, SRM)
- did the test have enough data to detect a meaningful effect (power and MDE)
- did variance reduction (CUPED) help

A Model Reports page shows your churn and forecasting results from the lab.

**Why it is first:**
- the statistics already exist and are tested in `applied-data-science-lab/01-experiment-analysis/abtest/`
- it is the fastest route to a live, deployed full-stack link on your resume

### What it proves

| Track | Proof |
|---|---|
| SWE | Django REST Framework API, async jobs (Celery on RabbitMQ), direct-to-S3 uploads, React 18 frontend, Kubernetes deployment with Helm, CI/CD |
| DS | correct experiment statistics, proven against SciPy and statsmodels, reproducing a real experiment |

**The interview story:** "Long analyses run as background jobs, so the API never blocks. Files go straight from the browser to S3, so the API never carries them. Every result is reproducible from the file's hash. The statistics are verified against SciPy to 1e-9."

### Resume lines this build must make true (SWE version)
- "Built a Django REST Framework API with Celery jobs on RabbitMQ, presigned S3 uploads, and a React 18 UI on Kubernetes."
- "A stats library matched to SciPy to 1e-9 with Hypothesis tests reproduces a 64,000-customer test (+7.66 pts, 95% CI 7.00 to 8.32); churn model AUC 0.77 vs 0.71 baseline."

**Stack line:** Python, Django REST Framework, Celery, RabbitMQ, React 18, AWS S3, Kubernetes, Helm, Hypothesis.

### Numbers already measured in the lab (the app must recompute them, never copy them)
- Hillstrom email test: 64,000 customers. Arms: men's email 21,307, women's email 21,387, no email 21,306. SRM p = 0.9037.
- Men's email vs no email, visit rate: 18.28% vs 10.62%, difference 0.07659 (7.66 pts), 95% CI 0.06995 to 0.08323 (Welch interval on the 0/1 outcome).
- CUPED with prior-year spend (`history`) on visits: correlation 0.067, variance removed 0.44%, which is why the app must say "not helpful here".
- Churn AUC 0.77 vs 0.71 and the forecasting results live in the lab JSON files (section 9).

---

## 2. Scope

### In scope
- **Uploads:** CSV upload up to 50 MB, straight from the browser to S3 with a presigned POST.
- **Column mapping step:** preview the first 20 rows, then pick the variant column, control label, metric column, metric type, an optional pre-period column, and the planned split.
- **Analysis job:** runs in Celery; results are stored and shareable by link; the same file with the same mapping returns the stored result.
- **Statistics:** 2 to 10 arms; each treatment is compared with control; Holm correction across comparisons.
- **Sample-size calculator.**
- **Model Reports page.**
- **One-click Hillstrom sample.**
- **Deployment:** a Kubernetes cluster (k3s) on one EC2 box, with a Helm chart, HTTPS and an autoscaled worker.

### Out of scope
User accounts, experiment assignment or randomization, real-time event ingestion, Bayesian methods, uplift models in the app (they stay in the lab), multiple metrics per analysis.

---

## 3. Architecture

```
Browser (React 18 SPA, served by nginx in the cluster)
   │  1. POST /api/uploads            -> presigned POST (S3 URL + fields), upload_id
   │  2. POST file straight to S3     (never through the API)
   │  3. POST /api/uploads/{id}/complete -> API checks the object (HEAD) and returns a 20-row preview (ranged GET)
   │  4. POST /api/analyses {upload_id, mapping} -> 202 + analysis_id
   │  5. GET  /api/analyses/{id} (poll every 1 s until SUCCEEDED or FAILED)
   ▼
Django + DRF API (gunicorn) ──enqueue──► RabbitMQ ──► Celery worker(s)
   │                                                 │ downloads the object from S3, computes sha256,
   │                                                 │ checks idempotency, DuckDB reads and validates the CSV,
   │                                                 │ abkit computes statistics, result saved
   ▼                                                 ▼
PostgreSQL  ◄──────────────────────────────────────── results (JSON) and job state
AWS S3: uploads/ (expire after 7 days), samples/hillstrom.csv
```

### Kubernetes (k3s) on one EC2 instance
- **Deployments:**
  - `web` (nginx serving the built SPA)
  - `api` (gunicorn + Django)
  - `worker` (Celery, with a HorizontalPodAutoscaler for 1–3 replicas at 70% CPU)
- **StatefulSets:** `postgres` (16) and `rabbitmq`, each with a PersistentVolumeClaim (k3s local-path storage).
- **Migrations:** a Job, run as a Helm pre-install/pre-upgrade hook (`manage.py migrate` plus `seed_samples`).
- **Ingress:** Traefik (bundled with k3s), with TLS from cert-manager and Let's Encrypt.
  - `p3.<domain>` → web
  - `p3.<domain>/api` → api
- **AWS access:** pods use the EC2 instance role through IMDSv2 (hop limit 2). **No AWS keys in the cluster.**

### Key design decisions (be able to explain each)
1. **Presigned POST, not presigned PUT:** a POST policy can enforce `content-length-range` (1 byte to 50 MB) and a fixed key prefix, so S3 rejects oversize files.
2. **Background jobs:** a 50 MB file can take seconds to tens of seconds. The API returns 202 at once, and the UI polls.
3. **Idempotency:**
   - the key is sha256(file bytes) + sha256(canonical mapping JSON)
   - if a SUCCEEDED analysis with the same key exists, the new analysis points to it (`reused_from`) and no work is redone
   - this is also why shared links are reproducible
4. **Safe retries:**
   - Celery runs with `acks_late=True` and `reject_on_worker_lost=True`
   - retries only on transient S3 or network errors (3 times, exponential backoff)
   - soft time limit 120 s, hard 150 s; never retried on bad-data errors
5. **DuckDB in the worker:**
   - reads the CSV with explicit column types
   - counts rows dropped (non-numeric metric, missing variant), aggregates per arm
   - hands numpy arrays to abkit
6. **Statistics live in their own package (`abkit`),** versioned and tested on its own. The web app is only a client of it.

---

## 4. Repo layout

**Repo name:** `experiment-analyzer` (public).

```
experiment-analyzer/
  CLAUDE.md  SPEC.md  README.md  VERSIONS.md  Makefile  .env.example
  abkit/                         # installable stats package (pyproject.toml), from the lab's abtest/stats.py
    src/abkit/__init__.py  stats.py  power.py  verdict.py
    tests/  test_equivalence.py  test_properties.py  test_edge_cases.py  test_lab_reproduction.py
  backend/
    pyproject.toml  manage.py
    config/  settings.py  urls.py  celery.py  wsgi.py
    analyzer/                    # Django app
      models.py  serializers.py  views.py  urls.py  tasks.py  storage.py  ingest.py  reports.py
      management/commands/seed_samples.py
      tests/
    reports/data/                # lab results JSON copied in + SOURCE.md (lab repo URL + commit)
    samples/hillstrom.csv        # + SOURCE.md (with sha256 from the lab)
  frontend/
    package.json  vite.config.ts  tsconfig.json
    src/  main.tsx  App.tsx  api/  pages/  components/  lib/
    tests/
  deploy/
    docker/  api.Dockerfile  worker.Dockerfile (or one image, two commands)  web.Dockerfile  nginx.conf
    compose.dev.yml              # postgres, rabbitmq, moto (S3), api, worker, web
    helm/experiment-analyzer/    # Chart.yaml, values.yaml, templates/
    aws/  s3-setup.sh  iam-policy.json  cors.json  lifecycle.json
    box/  bootstrap.sh           # k3s, helm, cert-manager, firewall
  .github/workflows/ci.yml  deploy.yml
  results/                       # evidence JSON (see section 11)
```

---

## 5. Data model (Django)

```python
class Upload(models.Model):
    id = UUIDField(primary_key=True)
    s3_key = CharField(max_length=300, unique=True)        # uploads/<uuid>.csv
    original_name = CharField(max_length=255)
    declared_size = BigIntegerField()
    size_bytes = BigIntegerField(null=True)                # from HEAD after upload
    status = CharField(choices=["PENDING", "UPLOADED", "EXPIRED"])
    columns = JSONField(null=True)                         # header from the preview
    created_at = DateTimeField(auto_now_add=True)

class Analysis(models.Model):
    id = UUIDField(primary_key=True)
    upload = ForeignKey(Upload, null=True, on_delete=SET_NULL)
    sample_name = CharField(max_length=50, blank=True)     # "hillstrom" for the one-click sample
    mapping = JSONField()                                  # validated mapping (see API)
    mapping_hash = CharField(max_length=64)
    input_sha256 = CharField(max_length=64, blank=True)    # filled by the worker
    status = CharField(choices=["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"], db_index=True)
    reused_from = ForeignKey("self", null=True, on_delete=SET_NULL)
    result = JSONField(null=True)                          # schema in section 7
    error_code = CharField(max_length=50, blank=True)      # e.g. SINGLE_ARM, NON_NUMERIC_METRIC
    error_message = TextField(blank=True)
    abkit_version = CharField(max_length=20, blank=True)
    git_sha = CharField(max_length=40, blank=True)
    created_at, started_at, finished_at = DateTimeField(...)
    class Meta:
        indexes = [Index(fields=["input_sha256", "mapping_hash", "status"])]
```

---

## 6. API contract (DRF; all JSON; errors use `{"error": {"code": str, "message": str}}`)

| Method and path | Request | Success | Errors |
|---|---|---|---|
| `GET /api/health` | — | 200 `{"status":"ok","db":true,"broker":true}` | 503 if DB or broker is down |
| `POST /api/uploads` | `{"filename":"x.csv","size":12345}` | 201 `{"upload_id","s3":{"url","fields"},"max_bytes":52428800,"expires_in":600}` | 413 if size > 50 MB; 415 if not `.csv` |
| `POST /api/uploads/{id}/complete` | — | 200 `{"upload_id","size_bytes","columns":[...],"preview":[[...] x20]}` | 404 if unknown; 409 if the object is missing in S3; 422 if not parseable as UTF-8 CSV |
| `POST /api/analyses` | `{"upload_id", "mapping":{"variant_col","control_label","metric_col","metric_type":"binary"|"continuous","pre_period_col":null|str,"planned_split":null|[floats],"alpha":0.05}}` | 202 `{"analysis_id","status":"QUEUED"}` (or 200 with the existing analysis if reused immediately) | 422 if a mapping column is not in the header, alpha is not in (0, 0.2], or planned_split does not sum to 1 |
| `POST /api/analyses/sample/hillstrom` | optional `{"metric_col":"visit"|"conversion"|"spend"}` | 202, same as above. Preset mapping: variant `segment`, control `No E-Mail`, pre-period `history`, binary for visit/conversion, continuous for spend | — |
| `GET /api/analyses/{id}` | — | 200 `{"id","status","mapping","result"|null,"error"|null,"input_sha256","abkit_version","git_sha","reused_from","timings"}` | 404 |
| `GET /api/analyses?limit=20` | — | 200, recent analyses (id, created, status, metric, verdict) | — |
| `POST /api/sample-size` | `{"base_rate":0.1,"mde_abs":0.01,"alpha":0.05,"power":0.8}` or `{"base_rate","n_per_arm","alpha","power"}` | 200 `{"n_per_arm" or "mde_abs", "curve":[{"n_per_arm","mde_abs"} x 30]}` | 422 |
| `GET /api/reports` | — | 200 `{"churn":{...},"forecasting":{...},"source":{"repo","commit"}}` | — |

**Rate limit:** DRF throttling, 30 analysis creations per hour per IP (anonymous). Return 429 with a friendly message.

---

## 7. Analysis job and result schema

### Worker steps (`analyzer/tasks.py: run_analysis(analysis_id)`)
1. Set the status to RUNNING with `started_at`.
2. Stream the S3 object to a temp file while computing sha256. Set `input_sha256`.
3. **Idempotency check:** look for a SUCCEEDED analysis with the same (`input_sha256`, `mapping_hash`).
   - If found: set `reused_from`, copy the result reference, mark SUCCEEDED and stop.
4. **DuckDB ingest** (`ingest.py`):
   - `read_csv` on the temp file, keeping only the mapped columns
   - cast the metric to DOUBLE (binary must be 0/1) and the pre-period column to DOUBLE if given
   - count dropped rows by reason (`null_variant`, `non_numeric_metric`, `non_binary_value`)
   - group by variant, returning counts and numpy arrays per arm
5. **Validation errors** fail with a code and message and are **never retried**:
   - fewer than 2 arms → `SINGLE_ARM`
   - control label not found → `CONTROL_NOT_FOUND`
   - more than 10 arms → `TOO_MANY_ARMS`
   - zero variance in every arm → `CONSTANT_METRIC`
   - any arm with n < 2 → `ARM_TOO_SMALL`
   - n < 30 in an arm → **warning only**
6. Call `abkit.analyze(arms, control, metric_type, pre_period, planned_split, alpha)` and save the result.
7. Set SUCCEEDED with `finished_at` and timings.

On a transient S3 error, retry. On an unexpected exception, set FAILED with `INTERNAL` and log the traceback (never return it to the client).

### Result JSON (stored in `Analysis.result`, typed on the frontend through a shared TypeScript type)
```json
{
  "arms": [{"label":"No E-Mail","n":21306,"mean":0.10617,"sd":0.308,"is_control":true}, ...],
  "rows": {"read":64000,"used":64000,"dropped":{"null_variant":0,"non_numeric_metric":0,"non_binary_value":0}},
  "srm": {"p":0.9037,"flagged":false,"planned_split":[0.333,0.333,0.334],"threshold":0.001},
  "comparisons": [{"treatment":"Mens E-Mail","diff":0.07659,"ci_low":0.06995,"ci_high":0.08323,
                   "rel_lift":0.7214,"p":1.4e-112,"p_holm":2.7e-112,"significant":true}, ...],
  "power": {"base_rate":0.10617,"n_per_arm":21306,"alpha":0.05,"power":0.8,"mde_abs":0.00836},
  "cuped": {"requested":true,"corr":0.067,"variance_removed":0.0044,"helpful":false,
            "message":"CUPED not helpful here (correlation 0.07, variance removed 0.4%)","adjusted":null},
  "warnings": [],
  "verdict": "Mens E-Mail increased visit rate by 7.66 percentage points (95% CI 7.00 to 8.32) vs No E-Mail."
}
```
The values above are illustrative of the shape. **The real values come from the run**, and `p_holm` will differ from the lab, which applied Holm across 6 tests while the app applies it across this analysis's comparisons.

### Rules
- **SRM:**
  - the expected split defaults to equal, or `planned_split` if given
  - `flagged` when p < 0.001
  - when flagged, the verdict starts with "Do not trust this result: the traffic split is off (SRM p = …)."
- **CUPED:**
  - computed only if a pre-period column is mapped
  - `helpful = |corr| >= 0.1 and variance_removed >= 0.05` (constants in `abkit/config`, documented in the README)
  - if helpful, `adjusted` holds the CUPED comparisons and the verdict mentions it
  - if not, `adjusted` is null and the message explains why
- **Verdict wording:**
  - binary metrics in percentage points; continuous metrics in metric units with the relative lift
  - "no detectable difference" when the CI includes 0, followed by "this test could detect differences of X or more"

---

## 8. `abkit` package (statistics)

Start from the lab's `01-experiment-analysis/abtest/stats.py`. **Keep the same formulas so the lab numbers reproduce.**

| Function | Source | Reference for the equivalence test | Tolerance |
|---|---|---|---|
| `diff_in_means(treat, ctrl, alpha)` (Welch) | lab | `scipy.stats.ttest_ind(equal_var=False)`: p-value, and `.confidence_interval()` for the CI | 1e-9 absolute |
| `srm_test(counts, expected_share)` | lab | `scipy.stats.chisquare` | 1e-12 |
| `holm(pvalues)` | lab | `statsmodels.stats.multitest.multipletests(method="holm")` | 1e-12 |
| `cuped(y, x)` | lab | theta equals the OLS slope of y on x (`numpy.polyfit` or statsmodels OLS); variance removed equals corr² | 1e-9 |
| `mde_two_proportions(base, n, alpha, power)` | lab | closed form, checked against `statsmodels.stats.power.NormalIndPower().solve_power` × sqrt(p(1−p)) | 1e-4 relative. statsmodels also counts the far tail, so the values are close but not identical; the README explains this. |
| `sample_size_two_proportions(base, mde, alpha, power)` | new | inverse of the MDE function; also checked by round-trip | round-trip within 1 unit |
| `analyze(...)` | new | orchestrates the above into the result schema | — |
| `verdict(result)` | new | template text; unit-tested strings | exact |

### Tests
1. **Equivalence:** parameterized over 20 seeded datasets per function (binary and continuous, unequal n). Record the max absolute difference per function in `results/validation.json`.
2. **Property tests (Hypothesis):**
   - the CI contains the point estimate
   - swapping treatment and control flips the sign of `diff` and swaps the CI
   - SRM: a 52/48 split at n = 100,000 gives p < 0.001; equal arms from a true 50/50 split give p ≥ 0.001 in at least 99 of 100 seeds
   - Holm-adjusted p ≥ raw p, and the order is preserved
   - CUPED variance removed is in [0, 1]
   - record the number of generated examples
3. **Edge cases:** single arm, zero variance, constant metric, n < 30 (warning), more than 10 arms, missing pre-period values (rows dropped and counted), non-binary values in a binary metric.
4. **Lab reproduction:**
   - run `analyze` on `samples/hillstrom.csv`: segment, control "No E-Mail", metric `visit`
   - assert the men's-vs-control diff, CI and SRM p equal the lab's `results.json` values (`effects.mens_visit`, `validity.srm_p`) to 1e-9
   - the test **reads** the expected values from `backend/reports/data/exp_results.json` and never types them

Version `abkit` with semver (`0.1.0`), and store the version on each analysis.

---

## 9. Model Reports (lab results shown in the app)

1. Copy into `backend/reports/data/`:
   - `02-churn-value/results/results.json` → `churn_results.json`
   - `02-churn-value/results/recalibration.json` → `churn_recalibration.json`
   - `03-forecasting/results/results.json` → `forecast_results.json`
   - `01-experiment-analysis/results/results.json` → `exp_results.json`
2. Write `SOURCE.md` with the lab repo URL and commit hash.
3. `reports.py` reads the files and returns:
   - **Churn card:**
     - test AUC of the selected model vs the recency baseline, with the CI on the gain (keys `test_selected`, `test_by_model`, `auc_gain_over_recency_ci`; **inspect the file and use the real keys**)
     - the targeting comparison (risk × value vs value only)
     - known limits, including the failed recalibration from `churn_recalibration.json`
   - **Forecasting card:** MASE per method across the rolling-origin backtests, with the winner highlighted and the number of backtests.
4. **Test:** every number the API returns equals the value at its key in the source JSON.

---

## 10. Frontend (React 18 + Vite + TypeScript)

### Libraries
- react 18.3.x (pinned, because the resume says React 18)
- react-router
- @tanstack/react-query v5
- react-hook-form + zod (@hookform/resolvers)
- recharts
- Tailwind CSS
- **Tests:** Vitest + React Testing Library + MSW (mock API)

### API layer
`src/api/` holds typed fetch functions and the result types. Query keys are `["analysis", id]`, etc. Polling uses `refetchInterval: (q) => terminal(q.state.data) ? false : 1000`.

### Pages
1. **Home (`/`):**
   - a hero line explaining the tool
   - **"Analyze a real 64,000-customer email test"** button → POST the sample → navigate to the result
   - an "Upload your own" button
   - the recent analyses list
2. **Upload (`/new`):**
   - drag-and-drop with a client-side check (.csv, ≤ 50 MB)
   - get the presigned POST, then upload with XMLHttpRequest so the **progress bar** works
   - call complete, show the preview table (20 rows) and the **mapping form** (RHF + Zod; dropdowns from the header; control label from the distinct values in the preview, editable; metric type; optional pre-period; optional planned split; alpha)
   - submit → navigate to `/analyses/:id`
3. **Analysis (`/analyses/:id`):**
   - **while running:** a status timeline (queued → running → done)
   - **once done:**
     - the **verdict sentence** (large)
     - SRM banner (green or red)
     - arms table
     - CI forest plot (Recharts: one row per treatment, a dot for the diff, a line for the CI, a zero line)
     - power card ("this test could detect X or more")
     - CUPED card
     - warnings
     - meta: rows read, used and dropped; input sha256 (shortened, copyable); abkit version; commit; "reused from" link
     - **Copy link** and **Download JSON** buttons
   - **on failure:** the error message, with what to fix
4. **Sample size (`/sample-size`):** a form that toggles between solving for n and solving for the MDE; result plus a curve chart.
5. **Model reports (`/reports`):** the two cards from section 9, with a source footnote.
6. **Method (`/method`):** a short explanation of each statistic, the SRM threshold, the CUPED rule, and a link to the repo.

### Quality
- **Accessibility:** labels on inputs, keyboard navigation, color plus text for the SRM banner.
- **Errors:** every API error shows its message.
- **Tests:**
  - mapping form validation
  - polling stops at a terminal state
  - verdict, SRM banner and CUPED card rendering
  - upload progress (mocked XHR)
- `tsc --noEmit` and eslint must be clean.

---

## 11. Evidence, results and resume bullets

`results/` files (JSON, each with commit, UTC date and command):
- **`validation.json`:** max absolute difference per abkit function vs its reference, number of Hypothesis examples, edge cases covered
- **`lab_reproduction.json`:** app vs lab for diff, CI and SRM p, and the absolute differences
- **`tests.json`:** counts per suite (abkit, backend, frontend)
- **`deploy_smoke.json`:** post-deploy sample analysis: time from submit to SUCCEEDED, the verdict, HTTP status codes
- **`hpa.json`** (optional): worker replica count during a 20-job burst

`make bullets` prints the resume bullets with every number taken from these files. Missing keys print MISSING.

**README evidence pack:**
1. what it does and the distinct engineering problem
2. live link, a GIF of the sample run, an architecture diagram
3. the numbers table generated from `results/`
4. how to run (`make dev`)
5. the testing approach and CI badge
6. design decisions (section 3)
7. limits

---

## 12. Accounts, setup and costs (you do these; Claude Code tells you what to click)

| Item | Notes |
|---|---|
| GitHub repo `experiment-analyzer` (public) | GitHub Container Registry for images (make the packages public, or add an image pull secret) |
| Local tools | Python 3.12, Node.js LTS, Docker Desktop, kubectl, Helm 4 (decided in Phase 0, was Helm 3; see VERSIONS.md), k3d (local Kubernetes for testing the chart), AWS CLI v2, Make |
| AWS | **Set a budget alarm first.** One S3 bucket. One EC2 instance (Ubuntu LTS, t3.medium class, 4 GB; k3s + Postgres + RabbitMQ + 3 app pods need the headroom; check current pricing). An Elastic IP. An IAM role for the instance. |
| Domain | Point `p3.<domain>` (A record) at the Elastic IP. Needed for HTTPS via Let's Encrypt. |
| Local S3 | `motoserver/moto` in Docker Compose for dev and CI. If presigned POST behaves differently from AWS there, use a real dev bucket instead. |
| Helm charts | Write your own templates for Postgres and RabbitMQ using the official images. Bitnami changed how it distributes free charts and images in 2025, so check before relying on them. |

**Security basics:**
- SSH by key only, plus fail2ban
- open only 22, 80 and 443 (never 6443, the Kubernetes API)
- unattended upgrades on
- S3 bucket private, with public access blocked
- an IAM role scoped to `s3:PutObject`, `s3:GetObject` and `s3:HeadObject` (covered by GetObject) on `uploads/*` and `samples/*` only
- secrets in Kubernetes Secrets, created from GitHub Actions secrets, never in `values.yaml`

---

## 13. Build phases (one phase per Claude Code session; commit at the end of each)

Every phase ends with a **Check**: output Claude Code must show you. Don't move on until you've seen it.

### Phase 0: repo and versions (½ day)
- Create the repo. Add `CLAUDE.md` and this file as `SPEC.md`. Write `.gitignore` and `.env.example`.
- Pin versions in `VERSIONS.md`: Python, Django (5.2 LTS), DRF, Celery, RabbitMQ image, Postgres 16, DuckDB, React 18.3.x, Vite, TanStack Query, Zod, Recharts, Tailwind, k3s, cert-manager. Use the exact versions Claude Code finds current and compatible.
- **Check:** the repo tree and `VERSIONS.md`.

### Phase 1: `abkit` (1 day)
- Extract the lab's stats into `abkit/`. Port the lab's tests. Add the equivalence, property, edge-case and lab-reproduction tests (section 8). Write `analyze()` and `verdict()`.
- **Check:**
  - pytest output with test counts
  - `results/validation.json`
  - `results/lab_reproduction.json` showing 7.66 pts and the CI 7.00–8.32 recomputed from the CSV

### Phase 2: Django API and uploads (1 day)
- Django 5.2 project, settings from environment variables, Postgres, models and migrations, DRF serializers and views for uploads (presigned POST through boto3 `generate_presigned_post` with a `content-length-range` condition), complete (HEAD + ranged GET preview), health, throttling.
- Compose services for dev: postgres, rabbitmq, moto, api.
- **Check:**
  - pytest (pytest-django): 201 for upload creation, 413, 415, 409 for complete without an object, 422 for a bad CSV
  - a manual curl walkthrough uploading a file to moto with the returned fields

### Phase 3: Celery jobs (1 day)
- Celery app, `run_analysis` task with `ingest.py` (DuckDB), idempotency, error codes, retries and time limits; `seed_samples` management command; sample endpoint; analyses list and detail; sample-size and reports endpoints.
- **Check:**
  - unit tests in eager mode
  - **an integration test with a real RabbitMQ and worker:** POST the sample → poll → SUCCEEDED with the reproduced numbers
  - a second POST of the same file and mapping returns a `reused_from` link
  - a bad-data file fails with the right code and is not retried

### Phase 4: React frontend (1.5 days)
- Vite + React 18 + TypeScript + Tailwind, router, API layer, all six pages (section 10), Vitest + RTL + MSW tests.
- **Check:**
  - screenshots of every page against the dev stack, including a real sample run and a real upload with the progress bar
  - test output; tsc and eslint clean

### Phase 5: Docker and CI (½ day)
- Dockerfiles (multi-stage; non-root user; small images), nginx config (SPA fallback, proxy `/api` in dev only), `compose.dev.yml` with all services, `make dev`, `make test`.
- `ci.yml` on every PR:
  - ruff, abkit tests, backend tests with postgres, rabbitmq and moto service containers
  - the integration test
  - frontend lint, tsc and tests
  - Docker builds for linux/amd64
  - `helm lint`, plus `helm template | kubeconform`
- **Check:** a green CI run link.

### Phase 6: Helm chart and local Kubernetes (1 day)
- Chart with:
  - web, api, worker Deployments (readiness and liveness probes, resource requests and limits)
  - postgres and rabbitmq StatefulSets with PVCs
  - Services, Ingress with TLS annotations
  - an HPA on the worker (min 1, max 3, CPU 70%)
  - a migration and seed Job as a pre-install/pre-upgrade hook
  - ConfigMap and Secret templates
- Test on k3d locally.
- **Check:**
  - `helm install` on k3d
  - `kubectl get pods` all Ready
  - a sample analysis succeeds through the ingress
  - `kubectl get hpa` output

### Phase 7: AWS and live deploy (1 day; you do the console and DNS steps when Claude Code asks)
- `deploy/aws/s3-setup.sh`: create the bucket, block public access, CORS (POST from `https://p3.<domain>` and `http://localhost:5173`; expose ETag), lifecycle (expire `uploads/` after 7 days), upload `samples/hillstrom.csv`.
- IAM role and policy, attached to the EC2 instance; set the IMDSv2 hop limit to 2.
- `deploy/box/bootstrap.sh`: k3s, Helm, cert-manager with a Let's Encrypt ClusterIssuer, firewall, fail2ban, unattended upgrades.
- `deploy.yml` on push to main:
  - build and push images tagged with the commit SHA to GHCR
  - SSH to the box and run `helm upgrade --install … --set image.tag=<sha>` (Kubernetes Secrets created from GitHub secrets)
  - run the smoke test (health + sample analysis) and write `results/deploy_smoke.json` as a workflow artifact
- **Check:**
  - `curl -I https://p3.<domain>` shows valid TLS
  - the smoke test output
  - the live sample analysis in the browser

### Phase 8: evidence and finish (½ day)
- README evidence pack (section 11), the GIF, the architecture diagram, the generated numbers table, `make bullets`.
- Optional: an HPA burst demo for `hpa.json`.
- **Check:** `make bullets` output, a link to the README, and a subagent review against "Done means" (section 14).

**Total:** about 8–9 working days part-time, which is 1.5–2 weeks.

### Prompts to paste into Claude Code (one per session)
1. "Read SPEC.md and CLAUDE.md. Do Phase 0 only. Propose exact pinned versions in VERSIONS.md and explain any compatibility concerns, then stop."
2. "Phase 1. The lab repo is at <path>. Plan in plan mode first: list the functions moving into abkit and every test you will add. Then build it and show pytest, validation.json and lab_reproduction.json."
3. "Phase 2 in plan mode, then build. Show the pytest output and a curl walkthrough of a presigned POST upload to moto."
4. "Phase 3 in plan mode, then build. Show the integration test with a real worker, the reuse case and a failing bad-data case."
5. "Phase 4. Build all six pages. Show screenshots of each page with real data from the dev stack, plus test output."
6. "Phase 5. Dockerfiles, compose, make targets and ci.yml. Open a PR and show the green run."
7. "Phase 6. Helm chart; install on k3d; show kubectl get pods, a sample analysis through the ingress and the HPA."
8. "Phase 7. Walk me through the AWS and DNS steps one at a time (I click), then write bootstrap.sh and deploy.yml, push, and show the smoke test."
9. "Phase 8. README evidence pack and make bullets. Then use a subagent to check the repo against Done means and list anything missing."

**Between phases:**
- read the diff
- run `make test` yourself once
- ask Claude Code "why" for anything you couldn't explain in an interview
- run `/clear` before the next phase

---

## 14. Done means (final checklist)
- [ ] `abkit`: equivalence tests within the tolerances in section 8; property and edge-case tests pass; `validation.json` written.
- [ ] Lab reproduction: diff, CI and SRM p match the lab to 1e-9; `lab_reproduction.json` written.
- [ ] Upload flow: presigned POST, oversize rejected by S3 and by the API, preview and mapping work.
- [ ] Analysis jobs: async through RabbitMQ and Celery; idempotent reuse; error codes; retries only on transient errors; time limits.
- [ ] Every endpoint in section 6 implemented and tested, including 413, 415, 409, 422, 429 and 404.
- [ ] Frontend: all six pages; polling; progress bar; accessible; tests pass; tsc and eslint clean.
- [ ] Model Reports numbers equal the lab JSON (test).
- [ ] CI green: lint, all test suites, integration test, image builds, helm lint, kubeconform.
- [ ] Helm chart works on k3d and on the EC2 k3s box; HPA present; migrations run as a hook.
- [ ] Live at `https://p3.<domain>` with valid TLS; no AWS keys in the cluster (instance role); S3 bucket private with a lifecycle rule.
- [ ] `results/*.json` present; README evidence pack complete; `make bullets` prints with no MISSING.

---

## 15. Interview prep (answers you should be able to give from your own code)
1. Why a presigned **POST** and not a PUT? (Size and prefix enforcement through the policy.)
2. What happens if a worker dies mid-job? (`acks_late` + `reject_on_worker_lost` → the message is redelivered; the idempotency key makes reprocessing safe.)
3. Why return 202 and poll instead of computing in the request? (Request timeouts, worker scaling, user experience.)
4. How does the idempotency key work, and why include the mapping hash?
5. Why Welch rather than Student's t? Why is the binary CI fine with Welch at this n?
6. What is SRM, and why p < 0.001? What would you do if it fires?
7. Why did CUPED not help on Hillstrom? (Correlation 0.067 → corr² ≈ 0.4% variance removed.)
8. How did you verify the statistics? (Equivalence to SciPy/statsmodels, property tests, lab reproduction.)
9. How does the HPA decide to scale, and what is its limit here? (CPU target; RabbitMQ queue depth would be better: KEDA, future work.)
10. How do the pods reach S3 without keys? (The EC2 instance role through IMDSv2 with hop limit 2.)
11. What did Claude Code write, and how did you check it? (Plan mode, diffs, tests at every phase.)
