"""abkit: experiment statistics for experiment-analyzer."""

from importlib.metadata import PackageNotFoundError, version

from .analysis import DROP_REASONS, AnalysisError, analyze
from .power import mde_two_means, mde_two_proportions, sample_size_two_proportions
from .stats import cuped, cuped_theta, diff_in_means, holm, srm_test
from .verdict import verdict

try:
    __version__ = version("abkit")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.1.0"

__all__ = [
    "DROP_REASONS",
    "AnalysisError",
    "__version__",
    "analyze",
    "cuped",
    "cuped_theta",
    "diff_in_means",
    "holm",
    "mde_two_means",
    "mde_two_proportions",
    "sample_size_two_proportions",
    "srm_test",
    "verdict",
]
