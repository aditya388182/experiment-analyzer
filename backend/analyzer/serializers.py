"""Request validation. Validation failures become 422 {"error": {"code": "VALIDATION_ERROR", ...}}."""

from __future__ import annotations

from rest_framework import serializers


class UploadCreateSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    size = serializers.IntegerField(min_value=1)
