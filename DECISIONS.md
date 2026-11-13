# DECISIONS.md

Choices made while building without the owner available. Each one: what, why, and how to undo it.

## D1. Python 3.12.16 installed from the python-build-standalone release by hand
`uv python install 3.12.16` fails on uv 0.13.1 ("No download found"): uv's built-in download list predates the
`20261110` python-build-standalone release that contains 3.12.16. Rather than move off the pinned uv, I downloaded
`cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`, checked it against the release's
`SHA256SUMS`, and unpacked it to `~/.local/share/uv/python/cpython-3.12.16-linux-x86_64-gnu/`, where uv finds it as a
managed interpreter (`uv python find 3.12.16` works). A newer uv would do this itself.

## D2. npm 11.19.1 (bundled with Node 24.22.3) instead of 11.6.2
VERSIONS.md lists npm 11.6.2 as "ships with the dev machine" (the laptop's Node 25). Node 24.22.3 bundles npm 11.19.1.
Downgrading npm below what the pinned Node ships with has no benefit, so `packageManager` is `npm@11.19.1` and
VERSIONS.md is updated.

## D3. Git author for commits on this box
The box had no git identity. I set a repo-local identity equal to the author of the existing commits
(`git config user.name/user.email` in `.git/config` only), so history stays consistent.

## D4. abkit: which lab code moves over
All of `abtest/stats.py` moves into `abkit/stats.py` with formulas unchanged (`srm_test`, `diff_in_means`,
`bootstrap_diff_ci`, `holm`, `cuped`, `regression_adjusted_effect`, `aa_false_positive_rate`); `mde_two_proportions`
moves to `abkit/power.py`. `uplift.py` and `sequential.py` stay in the lab (uplift models are out of scope, SPEC section 2).
The lab tests for those functions are ported; tests that import the lab's `run.py`, `uplift.py` or scikit-learn are not.
`cuped` gained a separate `cuped_theta(y, x)` helper; `cuped` calls it, and the expression is the same one the lab used.

## D5. MDE / sample-size equivalence: what "statsmodels" means at 1e-4 (a spec tolerance that did not hold as written)
SPEC section 8 says to check `mde_two_proportions` against `NormalIndPower().solve_power(...) x sqrt(p(1-p))` at
1e-4 relative. On 2 of 20 seeds that fails (1.24e-4 and 1.32e-4). The cause is statsmodels' root-finder, not our
formula: at statsmodels' own returned effect size, statsmodels' own power function gives 0.79990 instead of the requested
0.8. At *our* MDE, statsmodels' power function gives exactly target + far-tail (to 1e-9). The abkit formula was not
touched. The test now checks three things:
1. statsmodels `power()` at our MDE equals target power plus the far-tail term (1e-9 absolute);
2. our MDE vs statsmodels' MDE solved to full precision (brentq, xtol 1e-15) on statsmodels' power curve: 1e-4 relative (the spec's tolerance);
3. our MDE vs raw `solve_power` output: 1e-3 relative (recorded separately in validation.json).

For `sample_size_two_proportions` the spec's "round trip within 1 unit" holds exactly. The extra comparison with
statsmodels' smallest n differs by 2 at n = 817,099 (relative 2.4e-6) because statsmodels counts the far tail, so that
comparison uses max(1 unit, 1e-5 relative).

## D6. CUPED: pooled across all arms, with the lab's per-pair view alongside
`result.cuped.corr` / `variance_removed` / `theta` are computed on all arms pooled, and one theta adjusts every arm, which is the usual
multi-arm CUPED. The lab measured CUPED per treatment-vs-control pair (men's + no-email rows: corr 0.0667,
variance removed 0.44%). The result also carries `cuped.by_comparison` with that per-pair view, and the lab-reproduction
test checks it against the lab JSON. On Hillstrom the pooled corr is 0.065 and the per-pair corr is 0.067. Both are "not helpful".

## D7. Result schema additions (SPEC section 7 shows the shape; these fields are added, nothing removed)
- top level: `metric_col`, `metric_type`, `control_label`, `alpha` (the verdict template needs them)
- comparisons: `treat_mean`, `ctrl_mean`, `se`, `degenerate`; `rel_lift` is `null` when the control mean is 0
- srm: `observed_split`
- power: `sd` (control SD; used for continuous MDE), `base_rate` is `null` for continuous metrics, `mde_abs` is `null` when undefined (base rate 0 or 1, or zero SD)
- cuped: `pre_period_col`, `theta`, `by_comparison`
- rows.dropped: adds `null_pre_period` (SPEC section 8 edge case: missing pre-period rows are dropped and counted)
- `power.n_per_arm` is the smallest arm (conservative); on Hillstrom that is the control arm, as in the lab.
- `planned_split` order: the control first, then the other arms in ascending label order (the order arms appear in the result). A length mismatch fails with `PLANNED_SPLIT_MISMATCH`.
- Extra error codes: `PLANNED_SPLIT_MISMATCH`, `BAD_PLANNED_SPLIT`.
- Validation order: SINGLE_ARM, CONTROL_NOT_FOUND, TOO_MANY_ARMS, ARM_TOO_SMALL, CONSTANT_METRIC. ARM_TOO_SMALL is checked before CONSTANT_METRIC because a 1-row arm has no variance.
- When both arms of a comparison have zero variance (but others do not), the comparison is reported as degenerate (CI = point, p = 0 or 1) with a warning, instead of dividing by zero.
