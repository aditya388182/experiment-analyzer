"""Request validation. Validation failures become 422 {"error": {"code": "VALIDATION_ERROR", ...}}."""

from __future__ import annotations

from rest_framework import serializers


class UploadCreateSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    size = serializers.IntegerField(min_value=1)


class MappingSerializer(serializers.Serializer):
    variant_col = serializers.CharField(max_length=255)
    control_label = serializers.CharField(max_length=255, trim_whitespace=True)
    metric_col = serializers.CharField(max_length=255)
    metric_type = serializers.ChoiceField(choices=["binary", "continuous"])
    pre_period_col = serializers.CharField(max_length=255, allow_null=True, required=False, default=None)
    planned_split = serializers.ListField(
        child=serializers.FloatField(min_value=0, max_value=1),
        allow_null=True,
        required=False,
        default=None,
        min_length=2,
        max_length=10,
    )
    alpha = serializers.FloatField(required=False, default=0.05)

    def validate_alpha(self, value: float) -> float:
        if not 0 < value <= 0.2:
            raise serializers.ValidationError("alpha must be in (0, 0.2].")
        return value

    def validate_planned_split(self, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if any(v <= 0 for v in value):
            raise serializers.ValidationError("every share must be greater than 0.")
        if abs(sum(value) - 1.0) > 1e-6:
            raise serializers.ValidationError(f"shares must sum to 1 (they sum to {sum(value):.6g}).")
        return value

    def validate(self, attrs: dict) -> dict:
        cols = [attrs["variant_col"], attrs["metric_col"]] + (
            [attrs["pre_period_col"]] if attrs.get("pre_period_col") else []
        )
        if len(set(cols)) != len(cols):
            raise serializers.ValidationError("variant, metric and pre-period columns must be different columns.")
        header = self.context.get("columns")
        if header is not None:
            missing = [c for c in cols if c not in header]
            if missing:
                raise serializers.ValidationError(
                    {"mapping": f"column(s) not in the file header: {', '.join(missing)}."}
                )
        return attrs


class AnalysisCreateSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    mapping = serializers.DictField()


class SampleRequestSerializer(serializers.Serializer):
    metric_col = serializers.ChoiceField(choices=["visit", "conversion", "spend"], required=False, default="visit")


class SampleSizeSerializer(serializers.Serializer):
    base_rate = serializers.FloatField()
    mde_abs = serializers.FloatField(required=False)
    n_per_arm = serializers.IntegerField(required=False, min_value=2, max_value=1_000_000_000)
    alpha = serializers.FloatField(required=False, default=0.05)
    power = serializers.FloatField(required=False, default=0.8)

    def validate(self, attrs: dict) -> dict:
        if not 0 < attrs["base_rate"] < 1:
            raise serializers.ValidationError({"base_rate": "must be between 0 and 1 (exclusive)."})
        if not 0 < attrs["alpha"] <= 0.2:
            raise serializers.ValidationError({"alpha": "must be in (0, 0.2]."})
        if not 0.5 <= attrs["power"] < 1:
            raise serializers.ValidationError({"power": "must be in [0.5, 1)."})
        has_mde, has_n = "mde_abs" in attrs, "n_per_arm" in attrs
        if has_mde == has_n:
            raise serializers.ValidationError(
                "send exactly one of mde_abs (to solve for n) or n_per_arm (to solve for the MDE)."
            )
        if has_mde and not 0 < attrs["mde_abs"] < 1:
            raise serializers.ValidationError({"mde_abs": "must be between 0 and 1 (an absolute difference in rates)."})
        return attrs
