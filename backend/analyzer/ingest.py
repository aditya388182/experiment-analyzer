"""DuckDB ingest: read the CSV with explicit (VARCHAR) types, keep only the mapped columns, cast, count dropped
rows by reason, and hand per-arm numpy arrays to abkit."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from abkit import AnalysisError
from abkit.config import MAX_ARMS


@dataclass
class Ingested:
    arms: dict[str, np.ndarray]
    pre_period: dict[str, np.ndarray] | None
    rows_read: int
    dropped: dict[str, int] = field(default_factory=dict)


def _q(name: str) -> str:
    """Quote a column name as a DuckDB identifier."""
    return '"' + name.replace('"', '""') + '"'


def _lit(value: str) -> str:
    """A DuckDB string literal."""
    return "'" + value.replace("'", "''") + "'"


def read_header(path: Path) -> list[str]:
    """Header row parsed with Python's csv module (same rules as the preview)."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f), None)
    except UnicodeDecodeError as e:
        raise AnalysisError("BAD_CSV", "The file is not UTF-8 text. Save it as UTF-8 CSV.") from e
    if not header:
        raise AnalysisError("BAD_CSV", "The file has no header row.")
    header = [h.strip() for h in header]
    if len(set(header)) != len(header):
        raise AnalysisError("BAD_CSV", "Column names in the header must be unique.")
    return header


def ingest(path: Path, mapping: dict[str, Any], *, threads: int = 2, memory_limit: str = "512MB") -> Ingested:
    variant, metric = mapping["variant_col"], mapping["metric_col"]
    pre = mapping.get("pre_period_col")
    binary = mapping["metric_type"] == "binary"

    header = read_header(path)
    con = duckdb.connect(":memory:", config={"threads": threads, "memory_limit": memory_limit})
    try:
        try:
            # Explicit types: every column is declared VARCHAR from the header we parsed, and DuckDB's sniffer is
            # off. (With auto-detection on, a single ragged row late in the file was silently taken as the header.)
            # We cast ourselves so bad values are counted, not fatal. Views cannot take bound parameters; the path
            # is a worker-made temp file, inlined as an escaped literal.
            literal = "'" + str(path).replace("'", "''") + "'"
            columns = "{" + ", ".join(f"{_lit(c)}: 'VARCHAR'" for c in header) + "}"
            con.execute(
                f"CREATE TEMP VIEW src AS SELECT * FROM read_csv({literal}, header = true, auto_detect = false, "
                f"columns = {columns}, delim = ',', quote = '\"', escape = '\"', strict_mode = true)"
            )
        except duckdb.Error as e:
            raise AnalysisError("BAD_CSV", f"Could not read the CSV: {str(e).splitlines()[0]}") from e

        missing = [c for c in (variant, metric, pre) if c and c not in header]
        if missing:
            raise AnalysisError("MAPPING_COLUMN_MISSING", f"Column(s) not in the file header: {', '.join(missing)}.")

        pre_expr = f"TRY_CAST(NULLIF(TRIM({_q(pre)}), '') AS DOUBLE)" if pre else "NULL::DOUBLE"
        binary_check = "(y IS NOT NULL AND y NOT IN (0, 1))" if binary else "FALSE"
        has_pre = "TRUE" if pre else "FALSE"
        try:
            con.execute(f"""
                CREATE TEMP TABLE classified AS
                WITH typed AS (
                    SELECT NULLIF(TRIM({_q(variant)}), '') AS v,
                           TRY_CAST(NULLIF(TRIM({_q(metric)}), '') AS DOUBLE) AS y,
                           {pre_expr} AS x
                    FROM src
                )
                SELECT v, y, x,
                       CASE WHEN v IS NULL THEN 'null_variant'
                            WHEN y IS NULL OR isnan(y) OR isinf(y) THEN 'non_numeric_metric'
                            WHEN {binary_check} THEN 'non_binary_value'
                            WHEN {has_pre} AND (x IS NULL OR isnan(x) OR isinf(x)) THEN 'null_pre_period'
                            ELSE NULL END AS drop_reason
                FROM typed
            """)
            rows_read = con.execute("SELECT count(*) FROM classified").fetchone()[0]
            dropped = {
                "null_variant": 0,
                "non_numeric_metric": 0,
                "non_binary_value": 0,
                "null_pre_period": 0,
            }
            for reason, n in con.execute(
                "SELECT drop_reason, count(*) FROM classified WHERE drop_reason IS NOT NULL GROUP BY 1"
            ).fetchall():
                dropped[reason] = int(n)
            used = con.execute("SELECT count(*) FROM classified WHERE drop_reason IS NULL").fetchone()[0]
            if used == 0:
                detail = ", ".join(f"{k} {v}" for k, v in dropped.items() if v) or "the file has no data rows"
                raise AnalysisError("NO_USABLE_ROWS", f"No row has a usable variant and metric value ({detail}).")
            n_arms = con.execute("SELECT count(DISTINCT v) FROM classified WHERE drop_reason IS NULL").fetchone()[0]
            if n_arms > MAX_ARMS:
                raise AnalysisError(
                    "TOO_MANY_ARMS",
                    f"Found {n_arms} distinct values in '{variant}'; the maximum is {MAX_ARMS}. "
                    "Is this the right column?",
                )
            data = con.execute("SELECT v, y, x FROM classified WHERE drop_reason IS NULL ORDER BY v").fetchnumpy()
        except duckdb.Error as e:
            raise AnalysisError("BAD_CSV", f"Could not read the CSV: {str(e).splitlines()[0]}") from e
    finally:
        con.close()

    labels = np.asarray(data["v"], dtype=object)
    y = np.asarray(data["y"], dtype=np.float64)
    x = np.asarray(data["x"], dtype=np.float64) if pre else None
    arms: dict[str, np.ndarray] = {}
    pre_arrays: dict[str, np.ndarray] | None = {} if pre else None
    if len(labels):
        # rows are sorted by label, so each arm is one contiguous slice
        change = np.flatnonzero(labels[1:] != labels[:-1]) + 1
        starts = np.concatenate([[0], change])
        ends = np.concatenate([change, [len(labels)]])
        for s, e in zip(starts, ends, strict=True):
            label = str(labels[s])
            arms[label] = y[s:e]
            if pre_arrays is not None and x is not None:
                pre_arrays[label] = x[s:e]
    return Ingested(arms=arms, pre_period=pre_arrays, rows_read=int(rows_read), dropped=dropped)
