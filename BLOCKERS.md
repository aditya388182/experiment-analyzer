# BLOCKERS.md

Things that need the owner's accounts, money, secrets or settings. Everything else was built and tested locally.
Listed in the order to do them.

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
