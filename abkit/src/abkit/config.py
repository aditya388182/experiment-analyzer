"""Thresholds used by ``analyze``. Documented in the README and on the app's Method page."""

SRM_THRESHOLD = 0.001  # flag the traffic split when the chi-square p-value is below this
CUPED_MIN_ABS_CORR = 0.1  # CUPED is "helpful" only if |corr(y, x)| >= this ...
CUPED_MIN_VARIANCE_REMOVED = 0.05  # ... and it removes at least this share of the variance
SMALL_ARM_WARNING_N = 30  # warn (do not fail) when an arm has fewer rows than this
MIN_ARM_N = 2  # fail with ARM_TOO_SMALL below this
MAX_ARMS = 10
DEFAULT_POWER = 0.8
