# PROGRESS.md

Autonomous build log. If context is lost: re-read this file, DECISIONS.md and BLOCKERS.md, then continue with "Next".

## Toolchain (installed on the EC2 build box, 2026-11-13)

| Tool | Pinned | Installed (command output) |
|---|---|---|
| uv | 0.13.1 | `uv 0.13.1 (x86_64-unknown-linux-gnu)` |
| Python | 3.12.16 | `/home/ubuntu/.local/share/uv/python/cpython-3.12.16-linux-x86_64-gnu/bin/python3.12 --version` → `Python 3.12.16` |
| Node.js | 24.22.3 | `v24.22.3` |
| npm | 11.6.2 (VERSIONS.md) | `11.19.1` (bundled with Node 24.22.3; see DECISIONS.md D2) |
| kubectl | 1.36.x | `Client Version: v1.36.6` |
| Helm | 4.3.1 | `v4.3.1+gc0d08d0` |
| k3d | 5.9.0 | `k3d version v5.9.0` |
| kubeconform | 0.8.0 | `v0.8.0` |
| Docker | (box) | `Docker version 29.9.3, build 5457199`, `Docker Compose version v5.7.1` |

All downloads were checked against the publisher's SHA-256 checksums.

## Phases
