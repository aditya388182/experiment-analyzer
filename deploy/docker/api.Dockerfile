# One image for the API (gunicorn) and the worker (celery); the command differs.
# Build from the repo root: docker build -f deploy/docker/api.Dockerfile .
ARG PYTHON_IMAGE=python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv

# ---- build: resolve the locked dependencies into /opt/venv ----
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY abkit/pyproject.toml abkit/uv.lock abkit/README.md abkit/
COPY abkit/src abkit/src
COPY backend/pyproject.toml backend/uv.lock backend/
# --no-editable installs abkit as a normal package, so the runtime image does not need its source tree.
RUN cd backend && uv sync --frozen --no-dev --no-editable --no-install-project

# ---- runtime: no build tools, non-root ----
FROM ${PYTHON_IMAGE} AS runtime
ARG GIT_SHA=unknown
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --chown=10001:10001 backend/ /app/
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    GIT_SHA=${GIT_SHA}
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=4)"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "30", "--access-logfile", "-"]
