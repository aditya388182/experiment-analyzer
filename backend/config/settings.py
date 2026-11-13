"""Django settings. Everything that differs between environments comes from environment variables."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    UPLOAD_MAX_BYTES=(int, 52_428_800),
    PRESIGN_EXPIRES_SECONDS=(int, 600),
    S3_CREATE_BUCKET=(bool, False),
    DRF_NUM_PROXIES=(int, 0),
    ANALYSIS_RATE=(str, "30/hour"),
)

SECRET_KEY = env("DJANGO_SECRET_KEY")  # required; no default, so a missing secret fails loudly
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "analyzer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "analyzer.middleware.SimpleCorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# The throttle counters must be shared by every gunicorn worker and pod, so they live in Postgres.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
USE_I18N = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "analyzer.errors.exception_handler",
    "DEFAULT_THROTTLE_RATES": {"analysis_create": env("ANALYSIS_RATE")},
    "NUM_PROXIES": env("DRF_NUM_PROXIES") or None,
}

# Celery (RabbitMQ). VERSIONS.md concern 4: classic durable queue, prefetch 1 with late acks.
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
# Queue name is configurable so an integration run can share a broker with a dev stack without its jobs being
# taken by the other stack's worker.
CELERY_TASK_DEFAULT_QUEUE = env("CELERY_QUEUE", default="celery")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 120
CELERY_TASK_TIME_LIMIT = 150
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
# RabbitMQ 4.3 refuses transient non-exclusive queues (deprecated feature `transient_nonexcl_queues`), which is what
# Celery declares by default for remote control (pidbox) and gossip/mingle events. Exclusive queues are allowed.
# DECISIONS.md D9.
CELERY_CONTROL_QUEUE_EXCLUSIVE = True
CELERY_EVENT_QUEUE_EXCLUSIVE = True

# S3. In dev/CI the endpoints point at moto; in production they are empty and the EC2 instance role is used.
S3_BUCKET = env("S3_BUCKET")
AWS_REGION = env("AWS_REGION", default="us-east-1")
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="") or None
S3_PUBLIC_ENDPOINT_URL = env("S3_PUBLIC_ENDPOINT_URL", default="") or None
S3_CREATE_BUCKET = env("S3_CREATE_BUCKET")  # dev only: create the bucket (and CORS) if missing
UPLOAD_MAX_BYTES = env("UPLOAD_MAX_BYTES")
PRESIGN_EXPIRES_SECONDS = env("PRESIGN_EXPIRES_SECONDS")
SAMPLES_DIR = BASE_DIR / "samples"
REPORTS_DATA_DIR = BASE_DIR / "reports" / "data"

GIT_SHA = env("GIT_SHA", default="dev")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
