"""Minimal CORS for the dev setup where Vite (5173) calls the API (8000) directly.
In the cluster the SPA and the API share one origin, so CORS_ALLOWED_ORIGINS is empty there."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class SimpleCorsMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.headers.get("Origin")
        allowed = origin is not None and origin in settings.CORS_ALLOWED_ORIGINS
        if allowed and request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type"
            response["Access-Control-Max-Age"] = "600"
            response["Vary"] = "Origin"
        return response
