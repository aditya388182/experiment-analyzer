"""API views (SPEC.md section 6)."""

from __future__ import annotations

import logging

import abkit
import numpy as np
from abkit import mde_two_proportions, sample_size_two_proportions
from django.conf import settings
from django.db import connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from kombu import Connection
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import storage
from .errors import ApiError
from .mapping import canonical, mapping_hash
from .models import Analysis, Upload
from .preview import PREVIEW_BYTES, PreviewError, parse_preview
from .reports import reports
from .serializers import (
    AnalysisCreateSerializer,
    MappingSerializer,
    SampleRequestSerializer,
    SampleSizeSerializer,
    UploadCreateSerializer,
)
from .tasks import SAMPLE_KEYS, enqueue

log = logging.getLogger(__name__)


def _db_ok() -> bool:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - health check reports, never raises
        log.warning("health: database check failed", exc_info=True)
        return False


def _broker_ok() -> bool:
    try:
        with Connection(settings.CELERY_BROKER_URL, connect_timeout=2) as conn:
            conn.ensure_connection(max_retries=1, timeout=2)
        return True
    except Exception:  # noqa: BLE001
        log.warning("health: broker check failed", exc_info=True)
        return False


class HealthView(APIView):
    def get(self, request: Request) -> Response:
        db, broker = _db_ok(), _broker_ok()
        ok = db and broker
        return Response(
            {"status": "ok" if ok else "degraded", "db": db, "broker": broker},
            status=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class LiveView(APIView):
    """Liveness: the process answers HTTP. No dependency checks, so a broker outage does not restart the API pod."""

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class UploadCreateView(APIView):
    def post(self, request: Request) -> Response:
        s = UploadCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        filename: str = s.validated_data["filename"]
        size: int = s.validated_data["size"]
        if not filename.lower().endswith(".csv"):
            raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Only .csv files can be analyzed.")
        max_bytes = settings.UPLOAD_MAX_BYTES
        if size > max_bytes:
            msg = f"The file is {size:,} bytes; the limit is {max_bytes:,} bytes (50 MB)."
            raise ApiError(413, "FILE_TOO_LARGE", msg)
        upload = Upload(original_name=filename, declared_size=size)
        upload.s3_key = f"uploads/{upload.id}.csv"
        upload.save()
        expires = settings.PRESIGN_EXPIRES_SECONDS
        post = storage.presigned_post(upload.s3_key, max_bytes, expires)
        return Response(
            {
                "upload_id": str(upload.id),
                "s3": {"url": post["url"], "fields": post["fields"]},
                "max_bytes": max_bytes,
                "expires_in": expires,
            },
            status=status.HTTP_201_CREATED,
        )


class UploadCompleteView(APIView):
    def post(self, request: Request, upload_id: str) -> Response:
        upload = get_object_or_404(Upload, pk=upload_id)
        size = storage.head_size(upload.s3_key)
        if size is None:
            raise ApiError(409, "OBJECT_MISSING", "The file has not reached storage yet. Upload it, then try again.")
        if size > settings.UPLOAD_MAX_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE", f"The stored file is {size:,} bytes; the limit is 50 MB.")
        try:
            preview = parse_preview(storage.read_prefix(upload.s3_key, PREVIEW_BYTES), truncated=size > PREVIEW_BYTES)
        except PreviewError as e:
            raise ApiError(422, "BAD_CSV", str(e)) from e
        upload.size_bytes = size
        upload.columns = preview.columns
        upload.status = Upload.Status.UPLOADED
        upload.save(update_fields=["size_bytes", "columns", "status"])
        return Response(
            {"upload_id": str(upload.id), "size_bytes": size, "columns": preview.columns, "preview": preview.rows}
        )


# ---------------------------------------------------------------- analyses


SAMPLE_MAPPINGS = {
    metric: {
        "variant_col": "segment",
        "control_label": "No E-Mail",
        "metric_col": metric,
        "metric_type": "continuous" if metric == "spend" else "binary",
        "pre_period_col": "history",
        "planned_split": None,
        "alpha": 0.05,
    }
    for metric in ("visit", "conversion", "spend")
}


def analysis_summary(a: Analysis) -> dict:
    return {
        "id": str(a.id),
        "created_at": a.created_at.isoformat(),
        "status": a.status,
        "metric_col": a.mapping.get("metric_col"),
        "metric_type": a.mapping.get("metric_type"),
        "sample_name": a.sample_name or None,
        "file_name": a.upload.original_name if a.upload_id and a.upload else None,
        "verdict": (a.result or {}).get("verdict"),
        "reused_from": str(a.reused_from_id) if a.reused_from_id else None,
    }


def analysis_detail(a: Analysis) -> dict:
    return {
        "id": str(a.id),
        "status": a.status,
        "mapping": a.mapping,
        "sample_name": a.sample_name or None,
        "upload_id": str(a.upload_id) if a.upload_id else None,
        "file_name": a.upload.original_name if a.upload_id and a.upload else None,
        "result": a.result if a.status == Analysis.Status.SUCCEEDED else None,
        "error": {"code": a.error_code, "message": a.error_message} if a.status == Analysis.Status.FAILED else None,
        "input_sha256": a.input_sha256 or None,
        "abkit_version": a.abkit_version or None,
        "git_sha": a.git_sha or None,
        "reused_from": str(a.reused_from_id) if a.reused_from_id else None,
        "attempts": a.attempts,
        "created_at": a.created_at.isoformat(),
        "started_at": a.started_at.isoformat() if a.started_at else None,
        "finished_at": a.finished_at.isoformat() if a.finished_at else None,
        "timings": a.timings,
    }


def _create_analysis(*, mapping: dict, upload: Upload | None = None, sample_name: str = "") -> Response:
    canon = canonical(mapping)
    mhash = mapping_hash(canon)
    # Immediate reuse: the same stored object (same upload, or the same sample) with the same mapping already
    # succeeded, so the file hash is known to match. Other files are matched by hash in the worker.
    prior = Analysis.objects.filter(
        mapping_hash=mhash, status=Analysis.Status.SUCCEEDED, reused_from__isnull=True, abkit_version=abkit.__version__
    )
    prior = prior.filter(upload=upload) if upload is not None else prior.filter(sample_name=sample_name)
    original = prior.order_by("created_at").first()
    with transaction.atomic():
        a = Analysis.objects.create(upload=upload, sample_name=sample_name, mapping=canon, mapping_hash=mhash)
        if original is not None:
            now = timezone.now()
            a.status = Analysis.Status.SUCCEEDED
            a.reused_from = original
            a.result = original.result
            a.input_sha256 = original.input_sha256
            a.abkit_version = original.abkit_version
            a.git_sha = settings.GIT_SHA[:40]
            a.started_at = a.finished_at = now
            a.timings = {"queued_ms": 0, "total_ms": round((now - a.created_at).total_seconds() * 1000)}
            a.save()
            body = {"analysis_id": str(a.id), "status": a.status, "reused_from": str(original.id)}
            return Response(body, status=status.HTTP_200_OK)
        enqueue(a)
    return Response({"analysis_id": str(a.id), "status": a.status}, status=status.HTTP_202_ACCEPTED)


class AnalysisListCreateView(APIView):
    throttle_scope = "analysis_create"

    def get_throttles(self) -> list:
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request: Request) -> Response:
        try:
            limit = int(request.query_params.get("limit", 20))
        except ValueError as e:
            raise ApiError(422, "VALIDATION_ERROR", "limit must be an integer.") from e
        limit = max(1, min(limit, 100))
        rows = Analysis.objects.select_related("upload").order_by("-created_at")[:limit]
        return Response({"results": [analysis_summary(a) for a in rows]})

    def post(self, request: Request) -> Response:
        outer = AnalysisCreateSerializer(data=request.data)
        outer.is_valid(raise_exception=True)
        upload = Upload.objects.filter(pk=outer.validated_data["upload_id"]).first()
        if upload is None:
            raise ApiError(404, "NOT_FOUND", "Upload not found.")
        if upload.status != Upload.Status.UPLOADED:
            raise ApiError(409, "UPLOAD_NOT_COMPLETE", "Finish the upload (call /complete) before analyzing it.")
        m = MappingSerializer(data=outer.validated_data["mapping"], context={"columns": upload.columns})
        if not m.is_valid():
            raise ValidationError({"mapping": m.errors})
        return _create_analysis(mapping=m.validated_data, upload=upload)


class SampleAnalysisView(APIView):
    throttle_scope = "analysis_create"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request: Request, name: str) -> Response:
        if name not in SAMPLE_KEYS:
            raise ApiError(404, "NOT_FOUND", f"No sample named {name!r}.")
        s = SampleRequestSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        return _create_analysis(mapping=SAMPLE_MAPPINGS[s.validated_data["metric_col"]], sample_name=name)


class AnalysisDetailView(APIView):
    def get(self, request: Request, analysis_id: str) -> Response:
        a = Analysis.objects.select_related("upload").filter(pk=analysis_id).first()
        if a is None:
            raise ApiError(404, "NOT_FOUND", "Analysis not found.")
        return Response(analysis_detail(a))


# ---------------------------------------------------------------- sample size and reports


def _curve(base: float, n_center: int, alpha: float, power: float) -> list[dict]:
    lo, hi = max(2, n_center // 4), max(n_center * 4, 8)
    ns = sorted({int(round(x)) for x in np.geomspace(lo, hi, 30)})
    return [{"n_per_arm": n, "mde_abs": mde_two_proportions(base, n, alpha, power)} for n in ns]


class SampleSizeView(APIView):
    def post(self, request: Request) -> Response:
        s = SampleSizeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        base, alpha, power = d["base_rate"], d["alpha"], d["power"]
        if "mde_abs" in d:
            n = sample_size_two_proportions(base, d["mde_abs"], alpha, power)
            out = {"solved_for": "n_per_arm", "n_per_arm": n, "mde_abs": d["mde_abs"]}
        else:
            n = d["n_per_arm"]
            out = {"solved_for": "mde_abs", "n_per_arm": n, "mde_abs": mde_two_proportions(base, n, alpha, power)}
        out.update({"base_rate": base, "alpha": alpha, "power": power, "curve": _curve(base, n, alpha, power)})
        return Response(out)


class ReportsView(APIView):
    def get(self, request: Request) -> Response:
        return Response(reports())
