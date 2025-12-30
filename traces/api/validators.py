from datetime import datetime
from rest_framework import serializers

REQUIRED_FIELDS = {
    "trace_id",
    "span_id",
    "name",
    "kind",
    "start_time",
    "attributes",
}


def validate_trace(trace: dict):
    missing_fields = REQUIRED_FIELDS - trace.keys()
    if missing_fields:
        raise serializers.ValidationError(f"Missing fields: {missing_fields}")

    if not isinstance(trace["attributes"], dict):
        raise serializers.ValidationError("metadata must be an object")

    # ISO timestamps validation
    # datetime.fromisoformat(trace["started_at"].replace("Z", "+00:00"))
    # if trace.get("ended_at"):
    #     datetime.fromisoformat(trace["ended_at"].replace("Z", "+00:00"))
