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

### Phase 1: abkit — DONE
- `abkit/` package (0.1.0): lab `stats.py` ported with formulas unchanged; `power.py` (MDE, sample size, continuous MDE),
  `analysis.py` (`analyze`), `verdict.py`, `config.py`.
- Tests: equivalence (20 seeded datasets per function), Hypothesis properties, edge cases, ported lab tests, verdict
  strings, lab reproduction.
- **Check:** `make results-abkit` → `164 passed in 10.00s`.
  - `results/lab_reproduction.json`: men's vs no-email visit diff 0.07658956365153125 (7.66 pts), CI 0.06995314760976148
    to 0.083225979693301 (7.00 to 8.32), SRM p 0.9036929575604196. **abs diff to the lab = 0.0 on all 12 values checked**.
  - `results/validation.json`: max diffs: diff_in_means 2.2e-16, srm 0, holm 0, cuped 4.4e-16, MDE 2.6e-5 relative
    (vs converged statsmodels; see D5), sample size 7.1e-5 relative; 1,601 Hypothesis examples; 12 edge cases.
- Spec tolerance issue found and handled: DECISIONS.md D5 (statsmodels `solve_power` imprecision, not a formula change).
