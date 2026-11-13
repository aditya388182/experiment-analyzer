"""Every error leaves the API as {"error": {"code": str, "message": str}}. Tracebacks are logged, never returned."""

from __future__ import annotations

import logging
from typing import Any

from django.http import Http404, HttpRequest, JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger(__name__)


class ApiError(exceptions.APIException):
    """Raise from a view to return a specific status and code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(detail=message, code=code)
        self.status_code = status_code
        self.error_code = code
        self.message = message


def error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def _flatten(detail: Any, prefix: str = "") -> list[str]:
    if isinstance(detail, dict):
        out: list[str] = []
        for key, value in detail.items():
            name = key if key != "non_field_errors" else ""
            out.extend(_flatten(value, f"{prefix}.{name}" if prefix and name else (name or prefix)))
        return out
    if isinstance(detail, list):
        return [m for item in detail for m in _flatten(item, prefix)]
    return [f"{prefix}: {detail}" if prefix else str(detail)]


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, ApiError):
        return Response(error_body(exc.error_code, exc.message), status=exc.status_code)
    if isinstance(exc, exceptions.ValidationError):
        return Response(
            error_body("VALIDATION_ERROR", "; ".join(_flatten(exc.detail))),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if isinstance(exc, exceptions.Throttled):
        wait = f" Try again in {int(exc.wait)} seconds." if exc.wait else ""
        return Response(
            error_body("RATE_LIMITED", f"Too many analyses from your address; the limit is 30 per hour.{wait}"),
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if isinstance(exc, exceptions.ParseError):
        return Response(error_body("BAD_JSON", "The request body is not valid JSON."), status=400)
    if isinstance(exc, exceptions.UnsupportedMediaType):
        return Response(error_body("UNSUPPORTED_MEDIA_TYPE", "Send the request body as application/json."), status=415)
    if isinstance(exc, (Http404, exceptions.NotFound)):
        return Response(error_body("NOT_FOUND", "Not found."), status=404)
    response = drf_exception_handler(exc, context)
    if response is not None:
        code = getattr(exc, "default_code", "error").upper()
        message = str(getattr(exc, "detail", "Request failed."))
        response.data = error_body(code, message)
        return response
    log.exception("Unhandled error in %s", context.get("view"))
    return Response(error_body("INTERNAL", "Something went wrong on our side."), status=500)


def json_404(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse(error_body("NOT_FOUND", "Not found."), status=404)


def json_500(request: HttpRequest) -> JsonResponse:
    return JsonResponse(error_body("INTERNAL", "Something went wrong on our side."), status=500)
