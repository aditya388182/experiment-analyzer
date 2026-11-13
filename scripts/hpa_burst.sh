#!/usr/bin/env bash
# HPA burst demo: 20 distinct analyses submitted from a pod inside the cluster, while this script samples the worker
# HPA every 5 s. Writes results/hpa.json (via results_meta). Usage: scripts/hpa_burst.sh [namespace] [jobs]
set -euo pipefail
NS=${1:-experiment-analyzer}
JOBS=${2:-20}
REL=ea-experiment-analyzer
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SAMPLES=$(mktemp)
IMAGE=$(kubectl -n "$NS" get deploy "$REL-api" -o jsonpath='{.spec.template.spec.containers[0].image}')
CONTEXT=$(kubectl config current-context)

# A throwaway client pod from the api image (non-root, no service account token).
kubectl -n "$NS" run burst-client --image="$IMAGE" --image-pull-policy=IfNotPresent --restart=Never \
  --overrides='{"spec":{"automountServiceAccountToken":false,"securityContext":{"runAsNonRoot":true,"runAsUser":10001}}}' \
  --command -- sleep 3600 >/dev/null
kubectl -n "$NS" wait --for=condition=Ready pod/burst-client --timeout=120s >/dev/null
kubectl -n "$NS" cp "$ROOT/scripts/hpa_burst.py" burst-client:/tmp/hpa_burst.py

sample() {
  while true; do
    printf '%s %s %s\n' "$(date -u +%s)" \
      "$(kubectl -n "$NS" get hpa "$REL-worker" -o jsonpath='{.status.currentReplicas} {.status.currentMetrics[0].resource.current.averageUtilization}' 2>/dev/null)" \
      >> "$SAMPLES"
    sleep 5
  done
}
sample &
SAMPLER=$!
# Always stop the sampler and remove the client pod, even if the burst fails.
cleanup() { kill "$SAMPLER" 2>/dev/null || true; kubectl -n "$NS" delete pod burst-client --wait=false >/dev/null 2>&1 || true; }
trap cleanup EXIT
echo "sampling HPA every 5 s; running $JOBS jobs..."
BURST=$(kubectl -n "$NS" exec burst-client -- python /tmp/hpa_burst.py "http://$REL-api:8000" --jobs "$JOBS")
echo "$BURST"
echo "waiting 60 s more to record the scale-down start..."
sleep 60
cleanup
trap - EXIT

cd "$ROOT/backend"
BURST="$BURST" SAMPLES="$SAMPLES" CONTEXT="$CONTEXT" uv run python - <<'PY'
import json, os, sys
sys.path.insert(0, "../scripts")
import results_meta
rows = [l.split() for l in open(os.environ["SAMPLES"]) if l.strip()]
t0 = int(rows[0][0]) if rows else 0
series = [{"t_s": int(r[0]) - t0, "replicas": int(r[1]) if len(r) > 1 and r[1].isdigit() else None,
           "cpu_percent_of_request": int(r[2]) if len(r) > 2 and r[2].lstrip("-").isdigit() else None} for r in rows]
reps = [s["replicas"] for s in series if s["replicas"] is not None]
payload = {
    "environment": f"local k3d cluster ({os.environ['CONTEXT']}), not production",
    "hpa": {"min": 1, "max": 3, "target_cpu_percent": 70},
    "burst": json.loads(os.environ["BURST"]),
    "replicas_start": reps[0] if reps else None,
    "replicas_max": max(reps) if reps else None,
    "series": series,
}
p = results_meta.write("hpa.json", "scripts/hpa_burst.sh", payload)
print(f"wrote {p}: replicas {payload['replicas_start']} -> max {payload['replicas_max']}")
PY
