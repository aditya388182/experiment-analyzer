#!/usr/bin/env bash
# Phase 7: prepare a fresh Ubuntu 24.04 EC2 box for the app. Run once, as root, ON THE BOX:
#   sudo ACME_EMAIL=you@example.com bash bootstrap.sh
# Installs k3s (with its bundled Traefik), Helm, cert-manager + a Let's Encrypt ClusterIssuer; turns on the
# firewall (22, 80, 443 only), fail2ban and unattended upgrades; disables SSH password login.
# NOT RUN by Claude (needs your EC2 box): BLOCKERS.md B4.
set -euo pipefail
: "${ACME_EMAIL:?set ACME_EMAIL to the e-mail for the Lets Encrypt account}"

K3S_VERSION=v1.36.6+k3s1
HELM_VERSION=v4.3.1
CERT_MANAGER_VERSION=v1.21.3

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ufw fail2ban unattended-upgrades curl ca-certificates

# --- unattended security upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
systemctl enable --now unattended-upgrades

# --- SSH: keys only
install -d /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/10-keys-only.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
systemctl reload ssh

# --- fail2ban for sshd
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
EOF
systemctl enable --now fail2ban

# --- firewall: only 22, 80, 443 from the internet. Never 6443 (the Kubernetes API).
# k3s pod and service networks must be allowed, or in-cluster traffic is dropped.
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow from 10.42.0.0/16
ufw allow from 10.43.0.0/16
ufw --force enable

# --- k3s (bundled Traefik ingress, local-path storage, metrics-server for the HPA)
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" sh -s - \
  --write-kubeconfig-mode 600 --secrets-encryption
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
until kubectl get nodes 2>/dev/null | grep -q " Ready"; do sleep 3; done

# Keep the visitor's IP: with the default externalTrafficPolicy=Cluster, Traefik can see the node IP instead,
# and the API's per-IP rate limit (30 analyses/hour) would be shared by every visitor.
cat > /var/lib/rancher/k3s/server/manifests/traefik-config.yaml <<'EOF'
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    service:
      spec:
        externalTrafficPolicy: Local
EOF

# --- Helm (checksum-verified)
cd "$(mktemp -d)"
curl -fsSLO "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz"
echo "$(curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz.sha256sum" | cut -d' ' -f1)  helm-${HELM_VERSION}-linux-amd64.tar.gz" | sha256sum -c -
tar -xzf "helm-${HELM_VERSION}-linux-amd64.tar.gz"
install -m 0755 linux-amd64/helm /usr/local/bin/helm

# --- cert-manager + Let's Encrypt (HTTP-01 through Traefik)
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ${ACME_EMAIL}
    privateKeySecretRef:
      name: letsencrypt-prod-account
    solvers:
      - http01:
          ingress:
            ingressClassName: traefik
EOF

echo "Bootstrap done. k3s $(k3s --version | head -1); helm $(helm version --short)"
kubectl get nodes
kubectl -n cert-manager get pods
