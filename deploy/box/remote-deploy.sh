#!/usr/bin/env bash
# Runs ON THE BOX, called by .github/workflows/deploy.yml over SSH.
# Reads three secrets from stdin (one per line, never on a command line), applies the Kubernetes Secret, and runs
#   helm upgrade --install with the image tag of the commit being deployed.
# Env: APP_HOST, S3_BUCKET, AWS_REGION, SHA, OWNER, CHART_TGZ
set -euo pipefail
read -r DJANGO_SECRET_KEY
read -r POSTGRES_PASSWORD
read -r RABBITMQ_PASSWORD
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
NS=experiment-analyzer

kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create ns "$NS"
kubectl -n "$NS" create secret generic experiment-analyzer \
  --from-literal=DJANGO_SECRET_KEY="$DJANGO_SECRET_KEY" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=RABBITMQ_PASSWORD="$RABBITMQ_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

WORK=$(mktemp -d)
tar -xzf "$CHART_TGZ" -C "$WORK"
helm upgrade --install ea "$WORK/experiment-analyzer" -n "$NS" \
  --set image.registry="ghcr.io/$(echo "$OWNER" | tr '[:upper:]' '[:lower:]')" \
  --set image.tag="$SHA" \
  --set config.allowedHosts="$APP_HOST" \
  --set config.s3Bucket="$S3_BUCKET" \
  --set config.awsRegion="$AWS_REGION" \
  --set ingress.host="$APP_HOST" \
  --wait --timeout 10m
kubectl -n "$NS" get pods,hpa,ingress
