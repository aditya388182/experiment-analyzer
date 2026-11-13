"""Celery app. Broker: RabbitMQ (AMQP 0-9-1). Results are written to Postgres by the task, so no result backend."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("experiment_analyzer")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
