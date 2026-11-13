#!/usr/bin/env bash
# helm lint + helm template | kubeconform against Kubernetes 1.36 schemas (CI and `make lint`).
# Two value sets: production-shaped (ci/lint-values.yaml) and the local k3d install (ci/k3d-values.yaml).
set -euo pipefail
CHART=deploy/helm/experiment-analyzer
K8S=1.36.0
for values in ci/lint-values.yaml ci/k3d-values.yaml; do
  echo "== $values"
  helm lint "$CHART" --strict -f "$CHART/$values"
  helm template ea "$CHART" -f "$CHART/$values" \
    | kubeconform -strict -summary -kubernetes-version "$K8S"
done
# Schema-valid is not enough: Helm renders large numbers from values.yaml as floats ("5.24288e+07"), which the
# app's int() parsing rejects. Check the rendered ConfigMap holds plain integers.
rendered=$(helm template ea "$CHART" -f "$CHART/ci/lint-values.yaml" --show-only templates/configmap.yaml)
for key in UPLOAD_MAX_BYTES PRESIGN_EXPIRES_SECONDS DRF_NUM_PROXIES; do
  line=$(grep -E "^  $key:" <<<"$rendered")
  [[ $line =~ ^\ \ $key:\ \"[0-9]+\" ]] || { echo "ConfigMap $key is not a plain integer: $line" >&2; exit 1; }
done
echo "ConfigMap integers OK"
