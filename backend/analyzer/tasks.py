"""The analysis job (SPEC.md section 7).

Safety properties:
- acks_late + reject_on_worker_lost: if a worker dies mid-job the message goes back to the queue.
- idempotent: a redelivered or duplicate message for a finished analysis does nothing; an unfinished one is
  simply recomputed from the same S3 object and mapping, which gives the same answer.
- retries only transient S3/network errors (3 times, exponential backoff); bad data fails at once.
- soft time limit 120 s (we record TIMEOUT), hard limit 150 s (the worker process is killed).
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

import abkit
from abkit import AnalysisError
from celery import shared_task
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import storage
from .ingest import ingest
from .models import Analysis

log = logging.getLogger(__name__)

MAX_RETRIES = 3
SAMPLE_KEYS = {"hillstrom": "samples/hillstrom.csv"}


def object_key(analysis: Analysis) -> str:
    if analysis.sample_name:
        return SAMPLE_KEYS[analysis.sample_name]
    if analysis.upload is None:
        raise AnalysisError("UPLOAD_GONE", "The uploaded file for this analysis no longer exists.")
    return analysis.upload.s3_key


def find_reusable(input_sha256: str, mapping_hash: str, exclude_id: Any) -> Analysis | None:
    """The original (non-reused) SUCCEEDED analysis with the same file, mapping and abkit version."""
    return (
        Analysis.objects.filter(
            input_sha256=input_sha256,
            mapping_hash=mapping_hash,
            status=Analysis.Status.SUCCEEDED,
            abkit_version=abkit.__version__,
            reused_from__isnull=True,
        )
        .exclude(pk=exclude_id)
        .order_by("created_at")
        .first()
    )


def _ms(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


def _finish(analysis: Analysis, status: str, timings: dict[str, int], **fields: Any) -> None:
    now = timezone.now()
    timings["total_ms"] = round((now - analysis.created_at).total_seconds() * 1000)
    for k, v in fields.items():
        setattr(analysis, k, v)
    analysis.status = status
    analysis.finished_at = now
    analysis.timings = timings
    analysis.save()


def _fail(analysis: Analysis, timings: dict[str, int], code: str, message: str) -> None:
    _finish(analysis, Analysis.Status.FAILED, timings, error_code=code, error_message=message, result=None)


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=150,
    max_retries=MAX_RETRIES,
)
def run_analysis(self: Any, analysis_id: str) -> str:
    try:
        analysis = Analysis.objects.select_related("upload").get(pk=analysis_id)
    except Analysis.DoesNotExist:
        log.warning("run_analysis: %s does not exist; dropping message", analysis_id)
        return "missing"
    if analysis.is_terminal:  # duplicate or redelivered message for a finished job
        return analysis.status

    Analysis.objects.filter(pk=analysis.pk).update(attempts=F("attempts") + 1)
    analysis.refresh_from_db(fields=["attempts"])  # later full saves must not write back a stale count
    now = timezone.now()
    if analysis.started_at is None:
        analysis.started_at = now
    analysis.status = Analysis.Status.RUNNING
    analysis.abkit_version = abkit.__version__
    analysis.git_sha = settings.GIT_SHA[:40]
    analysis.save(update_fields=["status", "started_at", "abkit_version", "git_sha"])
    timings: dict[str, int] = {"queued_ms": round((analysis.started_at - analysis.created_at).total_seconds() * 1000)}

    try:
        with tempfile.TemporaryDirectory(prefix="analysis-") as tmp:
            path = Path(tmp) / "input.csv"
            t0 = time.monotonic()
            try:
                with path.open("wb") as fh:
                    dl = storage.download_with_sha256(object_key(analysis), fh, path)
            except Exception as e:
                if storage.is_transient(e):
                    if self.request.retries >= MAX_RETRIES:
                        _fail(analysis, timings, "STORAGE_UNAVAILABLE", "Storage was unreachable after 3 retries.")
                        return Analysis.Status.FAILED
                    log.warning("transient S3 error for %s (retry %s): %s", analysis_id, self.request.retries + 1, e)
                    raise self.retry(exc=e, countdown=2 ** (self.request.retries + 1)) from e
                if "NoSuchKey" in str(e) or "404" in str(e):
                    raise AnalysisError(
                        "OBJECT_MISSING", "The file is no longer in storage (uploads expire after 7 days)."
                    ) from e
                raise
            timings["download_ms"] = _ms(t0)
            analysis.input_sha256 = dl.sha256
            analysis.save(update_fields=["input_sha256"])

            original = find_reusable(dl.sha256, analysis.mapping_hash, analysis.pk)
            if original is not None:
                _finish(analysis, Analysis.Status.SUCCEEDED, timings, reused_from=original, result=original.result)
                return Analysis.Status.SUCCEEDED

            t0 = time.monotonic()
            data = ingest(path, analysis.mapping)
            timings["ingest_ms"] = _ms(t0)

        m = analysis.mapping
        t0 = time.monotonic()
        result = abkit.analyze(
            data.arms,
            m["control_label"],
            m["metric_type"],
            pre_period=data.pre_period,
            planned_split=m.get("planned_split"),
            alpha=m.get("alpha", 0.05),
            metric_name=m["metric_col"],
            pre_period_name=m.get("pre_period_col"),
            rows_read=data.rows_read,
            dropped=data.dropped,
        )
        timings["stats_ms"] = _ms(t0)
        _finish(analysis, Analysis.Status.SUCCEEDED, timings, result=result, error_code="", error_message="")
        return Analysis.Status.SUCCEEDED
    except AnalysisError as e:  # bad data: tell the user, never retry
        _fail(analysis, timings, e.code, e.message)
        return Analysis.Status.FAILED
    except SoftTimeLimitExceeded:
        _fail(analysis, timings, "TIMEOUT", "The analysis took longer than 120 seconds and was stopped.")
        return Analysis.Status.FAILED
    except Retry:
        raise
    except Exception:
        log.exception("run_analysis %s failed unexpectedly", analysis_id)
        _fail(analysis, timings, "INTERNAL", "Something went wrong on our side while analyzing this file.")
        return Analysis.Status.FAILED


def enqueue(analysis: Analysis) -> None:
    """Send the job only after the row is committed, so the worker can always find it."""
    transaction.on_commit(lambda: run_analysis.delay(str(analysis.pk)))
