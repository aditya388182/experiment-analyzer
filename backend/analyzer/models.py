"""Data model (SPEC.md section 5)."""

import uuid

from django.db import models


class Upload(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        UPLOADED = "UPLOADED"
        EXPIRED = "EXPIRED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    s3_key = models.CharField(max_length=300, unique=True)  # uploads/<uuid>.csv
    original_name = models.CharField(max_length=255)
    declared_size = models.BigIntegerField()
    size_bytes = models.BigIntegerField(null=True)  # from HEAD after upload
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    columns = models.JSONField(null=True)  # header from the preview
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Upload {self.id} ({self.status})"


class Analysis(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED"
        RUNNING = "RUNNING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(Upload, null=True, blank=True, on_delete=models.SET_NULL)
    sample_name = models.CharField(max_length=50, blank=True)  # "hillstrom" for the one-click sample
    mapping = models.JSONField()
    mapping_hash = models.CharField(max_length=64)
    input_sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True)
    reused_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reuses")
    result = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    abkit_version = models.CharField(max_length=20, blank=True)
    git_sha = models.CharField(max_length=40, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)  # task runs, including retries and redeliveries
    timings = models.JSONField(null=True, blank=True)  # milliseconds per step
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["input_sha256", "mapping_hash", "status"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Analysis {self.id} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.SUCCEEDED, self.Status.FAILED)
