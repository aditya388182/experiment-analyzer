"""Print every value in results/*.json as Markdown (for DONE.md), so no result is retyped by hand.

Usage: python3 scripts/done_results.py > /tmp/results.md   (or `make done-results` to refresh DONE.md in place)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def flatten(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(obj, dict):
        out: list[tuple[str, Any]] = []
        for k, v in obj.items():
            out.extend(flatten(v, f"{prefix}.{k}" if prefix else k))
        return out
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return [(f"{prefix}[{i}]", json.dumps(x, separators=(", ", ": "))) for i, x in enumerate(obj)]
    return [(prefix, obj)]


def render() -> str:
    parts = []
    for path in sorted((ROOT / "results").glob("*.json")):
        data = json.loads(path.read_text())
        parts.append(f"#### `results/{path.name}`\n\n| Key | Value |\n|---|---|")
        for key, value in flatten(data):
            shown = json.dumps(value) if not isinstance(value, str) else value
            parts.append(f"| `{key}` | {shown.replace('|', '\\|')} |")
        parts.append("")
    return "\n".join(parts)


def main() -> None:
    text = render()
    if "--write" in sys.argv:
        done = ROOT / "DONE.md"
        body = done.read_text()
        new = re.sub(
            r"(<!-- results:start -->)(.*?)(<!-- results:end -->)",
            lambda m: f"{m[1]}\n{text}\n{m[3]}",
            body,
            flags=re.S,
        )
        done.write_text(new)
    else:
        print(text)


if __name__ == "__main__":
    main()
