"""API views (SPEC.md section 6)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection
from django.shortcuts import get_object_or_404
from kombu import Connection
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import storage
from .errors import ApiError
from .models import Upload
from .preview import PREVIEW_BYTES, PreviewError, parse_preview
from .serializers import UploadCreateSerializer

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
