"""Test settings: defaults that point at the local dev stack (deploy/compose.dev.yml) or CI service containers.
Any of these can be overridden by real environment variables."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")
os.environ.setdefault("DATABASE_URL", "postgres://analyzer:change-me-dev-only@127.0.0.1:5432/analyzer")
os.environ.setdefault("CELERY_BROKER_URL", "amqp://analyzer:change-me-dev-only@127.0.0.1:5672//")
os.environ.setdefault("S3_BUCKET", "experiment-analyzer-test")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from .settings import *

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "true") == "true"
# S3 endpoints are set per test session by the moto server fixture in analyzer/tests/conftest.py.
