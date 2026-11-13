#!/usr/bin/env bash
# helm lint + helm template | kubeconform against Kubernetes 1.36 schemas (CI and `make lint`).
set -euo pipefail
CHART=deploy/helm/experiment-analyzer
K8S=1.36.0
helm lint "$CHART" --strict
helm lint "$CHART" --strict -f "$CHART/ci/k3d-values.yaml"
for values in "" "-f $CHART/ci/k3d-values.yaml"; do
  # shellcheck disable=SC2086
  helm template ea "$CHART" $values --set secrets.create=true \
    | kubeconform -strict -summary -kubernetes-version "$K8S" \
        -schema-location default \
        -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
done
