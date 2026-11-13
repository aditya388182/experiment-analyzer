#!/usr/bin/env bash
# Phase 2 Check: create an upload, POST the file straight to S3 (moto) with the returned fields, complete it.
# Usage: scripts/curl_walkthrough.sh [file.csv] [api base, default http://127.0.0.1:8000]
set -euo pipefail
FILE=${1:-backend/samples/hillstrom.csv}
API=${2:-http://127.0.0.1:8000}
SIZE=$(stat -c %s "$FILE")
NAME=$(basename "$FILE")

echo "## 1. GET /api/health"
curl -s -w ' -> HTTP %{http_code}\n' "$API/api/health"

echo "## 2. POST /api/uploads {filename: $NAME, size: $SIZE}"
CREATE=$(curl -s -X POST "$API/api/uploads" -H 'Content-Type: application/json' -d "{\"filename\":\"$NAME\",\"size\":$SIZE}")
echo "$CREATE" | jq '{upload_id, max_bytes, expires_in, s3: {url: .s3.url, fields: (.s3.fields | with_entries(if (.key|test("signature|policy|credential";"i")) then .value = (.value[0:24] + "...") else . end))}}'
ID=$(echo "$CREATE" | jq -r .upload_id)
URL=$(echo "$CREATE" | jq -r .s3.url)

echo "## 3. POST the file to S3 with the returned fields (the API never sees the bytes)"
ARGS=()
while IFS= read -r kv; do ARGS+=(-F "$kv"); done < <(echo "$CREATE" | jq -r '.s3.fields | to_entries[] | "\(.key)=\(.value)"')
curl -s -o /dev/null -w "S3 response: HTTP %{http_code}\n" "${ARGS[@]}" -F "file=@$FILE" "$URL"

echo "## 4. POST /api/uploads/$ID/complete"
curl -s -X POST "$API/api/uploads/$ID/complete" | jq -c '{upload_id, size_bytes, columns, preview_rows: (.preview|length), first_rows: .preview[0:3]}'

echo "## 5. Error cases"
curl -s -w ' -> HTTP %{http_code}\n' -X POST "$API/api/uploads" -H 'Content-Type: application/json' -d '{"filename":"big.csv","size":52428801}'
curl -s -w ' -> HTTP %{http_code}\n' -X POST "$API/api/uploads" -H 'Content-Type: application/json' -d '{"filename":"data.xlsx","size":10}'
ID2=$(curl -s -X POST "$API/api/uploads" -H 'Content-Type: application/json' -d '{"filename":"never.csv","size":10}' | jq -r .upload_id)
curl -s -w ' -> HTTP %{http_code}\n' -X POST "$API/api/uploads/$ID2/complete"
curl -s -w ' -> HTTP %{http_code}\n' -X POST "$API/api/uploads/00000000-0000-0000-0000-000000000000/complete"
