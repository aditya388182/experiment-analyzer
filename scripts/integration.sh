#!/usr/bin/env bash
# Integration test: real API + real RabbitMQ + real Celery worker, against a fresh `analyzer_it` database.
# Needs `make infra-up` (postgres, rabbitmq, moto). The API runs on 127.0.0.1:8001 so it does not clash with dev.
set -euo pipefail
cd "$(dirname "$0")/../backend"
set -a; . ../scripts/dev.env; set +a
export DATABASE_URL=postgres://analyzer:change-me-dev-only@127.0.0.1:5432/analyzer_it
export S3_BUCKET=experiment-analyzer-it
export CELERY_QUEUE=integration-$$   # own queue: a dev worker on the same broker must not take these jobs
export GIT_SHA=${GIT_SHA:-$(git rev-parse --short HEAD)}
LOGDIR=${LOGDIR:-$(mktemp -d)}

echo "== fresh database analyzer_it"
# Recreate the test database over TCP (works with Compose and with CI service containers).
uv run python - <<'PY'
import psycopg
with psycopg.connect("postgresql://analyzer:change-me-dev-only@127.0.0.1:5432/analyzer", autocommit=True) as c:
    c.execute("DROP DATABASE IF EXISTS analyzer_it WITH (FORCE)")
    c.execute("CREATE DATABASE analyzer_it")
PY
uv run python manage.py migrate -v0
uv run python manage.py createcachetable
uv run python manage.py seed_samples

echo "== start worker and API (logs in $LOGDIR)"
uv run celery -A config worker -l info --concurrency 2 -n "it@%h" >"$LOGDIR/worker.log" 2>&1 &
WORKER=$!
uv run gunicorn config.wsgi -b 127.0.0.1:8001 -w 2 >"$LOGDIR/api.log" 2>&1 &
APIPID=$!
cleanup() { kill "$APIPID" "$WORKER" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 60); do
  curl -sf http://127.0.0.1:8001/api/health >/dev/null && grep -q "ready" "$LOGDIR/worker.log" && break
  sleep 1
done

echo "== pytest -m integration"
INTEGRATION_API=http://127.0.0.1:8001 uv run pytest -m integration -s -v -p no:logging \
  ${JUNIT_XML:+--junitxml="$JUNIT_XML"} analyzer/tests/test_integration.py
echo "== worker log: task lines"
grep -E "Task analyzer.tasks.run_analysis\[.*\] (received|succeeded|retry)" "$LOGDIR/worker.log" | sed -E 's/^\[[^]]*\] //' || true
