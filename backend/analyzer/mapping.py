"""Mapping normalization and the idempotency key's mapping half."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAPPING_KEYS = ("variant_col", "control_label", "metric_col", "metric_type", "pre_period_col", "planned_split", "alpha")


def canonical(mapping: dict[str, Any]) -> dict[str, Any]:
    """Fill defaults and fix types so equal mappings serialize identically."""
    split = mapping.get("planned_split")
    return {
        "variant_col": str(mapping["variant_col"]),
        "control_label": str(mapping["control_label"]),
        "metric_col": str(mapping["metric_col"]),
        "metric_type": str(mapping["metric_type"]),
        "pre_period_col": mapping.get("pre_period_col") or None,
        "planned_split": [float(x) for x in split] if split else None,
        "alpha": float(mapping.get("alpha", 0.05)),
    }


def mapping_hash(mapping: dict[str, Any]) -> str:
    """sha256 of the canonical mapping JSON (sorted keys, no whitespace)."""
    blob = json.dumps(canonical(mapping), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()
