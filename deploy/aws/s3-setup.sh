#!/usr/bin/env bash
# Phase 7: create the private bucket, block public access, CORS, 7-day lifecycle on uploads/, upload the sample.
# Run on your laptop with AWS CLI v2 and an admin profile:  BUCKET=<name> APP_HOST=p3.<domain> deploy/aws/s3-setup.sh
# Idempotent: safe to rerun. Creates nothing but the bucket and its settings. Never run by Claude (BLOCKERS.md).
set -euo pipefail
: "${BUCKET:?set BUCKET}"
: "${APP_HOST:?set APP_HOST, e.g. p3.example.com}"
REGION=${AWS_REGION:-us-east-1}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "bucket $BUCKET exists"
elif [ "$REGION" = us-east-1 ]; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION"
fi

aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-ownership-controls --bucket "$BUCKET" \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-cors --bucket "$BUCKET" --cors-configuration "$(sed "s/APP_HOST/$APP_HOST/" "$HERE/cors.json")"
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration "file://$HERE/lifecycle.json"

want=$(grep -oE '[0-9a-f]{64}' "$ROOT/backend/samples/SOURCE.md" | head -1)
got=$(sha256sum "$ROOT/backend/samples/hillstrom.csv" | cut -d' ' -f1)
[ "$want" = "$got" ] || { echo "hillstrom.csv sha256 mismatch" >&2; exit 1; }
aws s3 cp "$ROOT/backend/samples/hillstrom.csv" "s3://$BUCKET/samples/hillstrom.csv" --content-type text/csv

sed "s/BUCKET_NAME/$BUCKET/g" "$HERE/iam-policy.json" > "$HERE/iam-policy.rendered.json"
echo "Done. IAM policy for the instance role written to deploy/aws/iam-policy.rendered.json"
aws s3api get-public-access-block --bucket "$BUCKET"
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET"
