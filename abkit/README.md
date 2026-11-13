# abkit

Experiment statistics used by experiment-analyzer. Formulas come from the lab's `abtest/stats.py` unchanged.

- `stats.py`: Welch difference in means, SRM chi-square, Holm, CUPED, regression adjustment, bootstrap, A/A check
- `power.py`: minimum detectable effect and sample size (normal approximation)
- `analysis.py`: `analyze()` builds the result JSON the app stores
- `verdict.py`: the plain-English verdict sentence
- `config.py`: thresholds (SRM 0.001; CUPED helpful when |corr| >= 0.1 and variance removed >= 5%)

Run the tests with `uv run pytest`.
