# BLOCKERS.md

Things that need the owner's accounts, money, secrets or settings. Everything else was built and tested locally.
**Phase 7 in order: B3 → B4 → B5 → B6 → B7 → B1 → B2 → B8.** B1 and B2 are listed first only because they were found first.

## B1. moto does not enforce the presigned POST policy: verify against a real S3 bucket (Phase 7)
Found in Phase 2 (VERSIONS.md concern 8, SPEC section 12). Against `motoserver/moto:5.2.5`, a presigned POST with
`["content-length-range", 1, 10]` accepted a 50-byte body (HTTP 204), and a POST that changed the `key` field outside
the signed key was also accepted. moto does not check the policy.

What is tested locally instead:
- the signed policy (base64 JSON in the `policy` field) contains `content-length-range [1, 52428800]` and the exact key (unit test);
- the API rejects declared sizes over 50 MB (413) and, on `/complete`, rejects objects whose HEAD size is over 50 MB (413).

**To do with a real bucket (after `deploy/aws/s3-setup.sh`):** run `make s3-policy-check S3_BUCKET=<your bucket>`
with credentials allowed to `s3:PutObject` on `uploads/*`. It posts a 50 MB + 1 byte file and expects S3's
`EntityTooLarge` (400). Paste the output into `results/` as evidence.

## B2. A green CI run needs the repo pushed to GitHub (Phase 5 Check)
`.github/workflows/ci.yml` is written, every action is pinned by commit SHA, and the YAML was checked to parse with
every `uses:` pinned. Every command in it was run locally with the same versions (`make lint`, `make test`,
`make test-integration`, `make build-images`, `scripts/helm_check.sh`); see PROGRESS.md. I did not push, so there
is no CI run link yet. (actionlint could not be run on the box: running a downloaded binary was blocked, so the
GitHub-specific syntax is only checked by a YAML parse.)

**What you do:**
1. Push the repo (or open a PR): `git push -u origin main`.
2. GitHub → the repo → **Actions** tab → the `ci` run. All 7 jobs (python-lint, abkit, backend, frontend, images ×2,
   helm) should be green. If a job fails on GitHub but passes locally, paste me the log.
3. Copy the run URL into the README's CI badge section (Phase 8 left a placeholder).

## B3. AWS account basics and the S3 bucket (Phase 7, step 1)
Files are ready: `deploy/aws/s3-setup.sh`, `cors.json`, `lifecycle.json`, `iam-policy.json` (written, syntax-checked, not run).
1. AWS console → **Billing and Cost Management → Budgets → Create budget** → "Monthly cost budget", amount e.g. 20 USD,
   your e-mail. Do this first.
2. Pick a globally unique bucket name, e.g. `experiment-analyzer-<random>`, and your domain host, e.g. `p3.<domain>`.
3. On your laptop (AWS CLI v2, an admin profile):
   `BUCKET=<bucket> APP_HOST=p3.<domain> AWS_REGION=us-east-1 deploy/aws/s3-setup.sh`
   It creates the private bucket (public access blocked, owner-enforced, SSE-S3), CORS (POST from `https://p3.<domain>` and
   `http://localhost:5173`, exposes ETag), the 7-day expiry on `uploads/`, uploads `samples/hillstrom.csv` after checking
   its sha256, and writes `deploy/aws/iam-policy.rendered.json`.

## B4. EC2 box, instance role, IMDSv2 hop limit, Elastic IP (Phase 7, step 2)
1. **IAM → Policies → Create policy → JSON**: paste `deploy/aws/iam-policy.rendered.json` → name `experiment-analyzer-s3`.
2. **IAM → Roles → Create role** → trusted entity "AWS service", use case **EC2** → attach `experiment-analyzer-s3` →
   name `experiment-analyzer-ec2`.
3. **EC2 → Launch instance**: Ubuntu Server 24.04 LTS, `t3.medium` (4 GB), 30 GB gp3, your SSH key pair,
   **IAM instance profile = experiment-analyzer-ec2**. Security group inbound: **22 from your IP only, 80 and 443 from
   anywhere. Not 6443.** Advanced details → Metadata version **V2 only**, metadata response hop limit **2**.
   (Existing instance: `aws ec2 modify-instance-metadata-options --instance-id <id> --http-tokens required --http-put-response-hop-limit 2`.)
4. **EC2 → Elastic IPs → Allocate** → Associate with the instance.
5. Copy the bootstrap script to the box and run it:
   `scp deploy/box/bootstrap.sh ubuntu@<eip>:` then `ssh ubuntu@<eip> 'sudo ACME_EMAIL=<your e-mail> bash bootstrap.sh'`.
   It installs k3s v1.36.6+k3s1, Helm v4.3.1, cert-manager v1.21.3 with a `letsencrypt-prod` ClusterIssuer, and turns on
   ufw (22/80/443), fail2ban, unattended upgrades and key-only SSH.
6. Check that pods can reach S3 through the instance role (no keys):
   `ssh ubuntu@<eip> 'sudo k3s kubectl run awscheck --rm -it --restart=Never --image=amazon/aws-cli -- s3 ls s3://<bucket>/samples/'`
   It should list `hillstrom.csv`. If it hangs, the hop limit is still 1.

## B5. DNS (Phase 7, step 3)
At your DNS provider, add an **A record**: `p3` → the Elastic IP. Wait until `dig +short p3.<domain>` prints the IP.
Let's Encrypt HTTP-01 needs this before the first deploy.

## B6. GitHub settings and secrets (Phase 7, step 4)
Repo → **Settings → Secrets and variables → Actions**:
- Secrets: `SSH_HOST` (the Elastic IP), `SSH_USER` (`ubuntu`), `SSH_PRIVATE_KEY` (a new deploy key: run
  `ssh-keygen -t ed25519 -f deploy_key -N ""`, append `deploy_key.pub` to `~/.ssh/authorized_keys` on the box, paste
  `deploy_key` here), `SSH_KNOWN_HOSTS` (output of `ssh-keyscan -t ed25519 <eip>`),
  `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `RABBITMQ_PASSWORD` (generate each with `openssl rand -hex 32`;
  hex keeps them URL-safe inside DATABASE_URL).
- Variables: `APP_HOST` = `p3.<domain>`, `S3_BUCKET` = your bucket, `AWS_REGION` = `us-east-1`.
- Settings → **Environments → New environment** `production` (deploy.yml uses it; you can add yourself as a required reviewer).
- After the first push, GitHub → your profile → **Packages** → `experiment-analyzer-api` and `-web` → Package settings →
  **Change visibility → Public** (or add an image pull secret and set `imagePullSecrets` in the chart values).

## B7. First deploy and the Phase 7 Check
1. `git push -u origin main`. `ci` runs (B2), then `deploy` builds and pushes images to GHCR, SSHes to the box,
   creates the Kubernetes Secret from the GitHub secrets, runs `helm upgrade --install`, and the smoke job writes
   `results/deploy_smoke.json` as a workflow artifact.
2. Check: `curl -I https://p3.<domain>` shows HTTP/2 200 with a valid Let's Encrypt certificate;
   `ssh ubuntu@<eip> 'sudo k3s kubectl -n experiment-analyzer get pods,hpa,ingress,certificate'`.
3. Download the `deploy_smoke` artifact and commit it as `results/deploy_smoke.json`; then run `make bullets` (it will
   no longer print MISSING for the deploy numbers).
4. Optional: `make hpa-burst BASE_URL=https://p3.<domain>` while watching `kubectl get hpa -w`, for `results/hpa.json`.

## B8. Lab repo URL and commit (Model Reports source)
`backend/reports/data/SOURCE.md` and `GET /api/reports` say "lab build of 2026-11-05 (lab_inputs/)" because the lab repo
was not pushed. When it is, set `REPORTS_SOURCE_REPO` / `REPORTS_SOURCE_COMMIT` in `backend/analyzer/reports.py` and
update SOURCE.md.
