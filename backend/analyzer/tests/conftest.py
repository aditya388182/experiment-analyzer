"""Fixtures: a real moto S3 server over HTTP (so presigned POSTs are real HTTP requests) and an API client."""

from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest
from django.conf import settings
from moto.server import ThreadedMotoServer
from rest_framework.test import APIClient

from analyzer import storage


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def moto_endpoint() -> Iterator[str]:
    port = _free_port()
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    server.start()
    yield f"http://127.0.0.1:{port}"
    server.stop()


@pytest.fixture(autouse=True)
def s3(request: pytest.FixtureRequest) -> Iterator[str | None]:
    """Every unit test gets a fresh, empty bucket on an in-process moto server. Integration tests talk HTTP to
    the real stack instead, so they get nothing here."""
    if request.node.get_closest_marker("integration"):
        yield None
        return
    moto_endpoint = request.getfixturevalue("moto_endpoint")
    settings.S3_ENDPOINT_URL = moto_endpoint
    settings.S3_PUBLIC_ENDPOINT_URL = moto_endpoint
    settings.S3_CREATE_BUCKET = True
    storage.reset_clients()
    import requests

    requests.post(f"{moto_endpoint}/moto-api/reset", timeout=5)
    storage.ensure_bucket()
    yield moto_endpoint
    storage.reset_clients()


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def seeded(s3: str) -> None:
    from django.core.management import call_command

    call_command("seed_samples", verbosity=0)


@pytest.fixture(autouse=True)
def _clear_cache(request: pytest.FixtureRequest) -> Iterator[None]:
    if not request.node.get_closest_marker("integration"):
        from django.core.cache import cache

        cache.clear()
    yield
