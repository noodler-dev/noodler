from datetime import datetime

REQUIRED_FIELDS = {
    "trace_id",
    "span_id",
    "name",
    "kind",
    "start_time",
    "attributes",
}


def validate_span(span: dict):
    missing = REQUIRED_FIELDS - span.keys()
    if missing:
        raise ValueError(f"Missing fields: {missing}")

    if not isinstance(span["attributes"], dict):
        raise ValueError("attributes must be an object")

    # ISO timestamps validation
    datetime.fromisoformat(span["start_time"].replace("Z", "+00:00"))
    if span.get("end_time"):
        datetime.fromisoformat(span["end_time"].replace("Z", "+00:00"))
