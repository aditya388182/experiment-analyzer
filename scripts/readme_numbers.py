"""Replace the README numbers table (between the numbers markers) with `bullets.py --markdown-table` output."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
readme = ROOT / "README.md"
table = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "bullets.py"), "--markdown-table"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
text = readme.read_text()
new = re.sub(
    r"(<!-- numbers:start -->)(.*?)(<!-- numbers:end -->)", lambda m: f"{m[1]}\n{table}\n{m[3]}", text, flags=re.S
)
if new == text and table not in text:
    sys.exit("numbers markers not found in README.md")
readme.write_text(new)
print(table)
