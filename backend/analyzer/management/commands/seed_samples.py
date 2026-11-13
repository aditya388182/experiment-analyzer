"""Put the one-click sample datasets in S3 (samples/<name>.csv). Safe to run on every deploy (Helm hook).

The local file's sha256 must match samples/SOURCE.md; the upload is skipped when S3 already holds an object
of the same size. In dev/CI (S3_CREATE_BUCKET=true) the bucket and its CORS rule are created first.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from analyzer import storage
from analyzer.tasks import SAMPLE_KEYS


def expected_sha256(samples_dir: Path) -> str:
    m = re.search(r"sha256:\s*([0-9a-f]{64})", (samples_dir / "SOURCE.md").read_text())
    if not m:
        raise CommandError("samples/SOURCE.md has no sha256 line")
    return m.group(1)


class Command(BaseCommand):
    help = "Upload sample datasets to S3 if missing"

    def handle(self, *args: Any, **options: Any) -> None:
        if settings.S3_CREATE_BUCKET:
            storage.ensure_bucket()
        samples_dir = Path(settings.SAMPLES_DIR)
        want = expected_sha256(samples_dir)
        for name, key in SAMPLE_KEYS.items():
            path = samples_dir / f"{name}.csv"
            got = hashlib.sha256(path.read_bytes()).hexdigest()
            if got != want:
                raise CommandError(f"{path} sha256 {got} does not match SOURCE.md {want}")
            size = path.stat().st_size
            if storage.head_size(key) == size:
                self.stdout.write(f"{key}: already present ({size} bytes)")
                continue
            storage.put_file(key, path)
            self.stdout.write(self.style.SUCCESS(f"{key}: uploaded {size} bytes (sha256 {got[:12]}...)"))
