import base64
import json
from datetime import datetime
from django.utils import timezone


def convert_nano_to_datetime(nano_timestamp: int) -> datetime:
    return datetime.fromtimestamp(nano_timestamp / 1e9, timezone.UTC)


def extract_attribute_value(attr: dict) -> any:
    value_dict = attr.get("value", {})

    if "string_value" in value_dict:
        return value_dict["string_value"]
    elif "int_value" in value_dict:
        return int(value_dict["int_value"])
    elif "bool_value" in value_dict:
        return value_dict["bool_value"]
    elif "double_value" in value_dict:
        return float(value_dict["double_value"])
    elif "array_value" in value_dict:
        # Recursively extract values from array
        values = value_dict["array_value"].get("values", [])
        return [extract_attribute_value({"value": val}) for val in values]
    elif "bytes_value" in value_dict:
        return value_dict["bytes_value"]
    else:
        return None


def parse_attributes(trace_attributes: list) -> dict:
    result = {}

    if not trace_attributes:
        return result

    for attr in trace_attributes:
        key = attr.get("key")
        value = extract_attribute_value(attr)
        if key:
            result[key] = value

    return result


def extract_gen_ai_fields(span_attributes: dict) -> dict:
    # Mapping from protobuf attribute keys to Span model field names
    field_mapping = {
        "gen_ai.provider.name": "provider_name",
        "gen_ai.operation.name": "operation_name",
        "gen_ai.request.model": "request_model",
        "gen_ai.request.max_tokens": "max_tokens",
        "gen_ai.request.top_p": "top_p",
        "gen_ai.response.id": "response_id",
        "gen_ai.response.model": "response_model",
        "gen_ai.response.finish_reasons": "finished_reasons",
        "gen_ai.usage.input_tokens": "input_tokens",
        "gen_ai.usage.output_tokens": "output_tokens",
        "gen_ai.system_instructions": "system_instructions",
        "gen_ai.input.messages": "input_messages",
        "gen_ai.output.messages": "output_messages",
    }

    result = {}

    for proto_key, model_key in field_mapping.items():
        if proto_key not in span_attributes:
            continue

        value = span_attributes[proto_key]

        # Handle JSON string parsing for messages
        if model_key in ("input_messages", "output_messages"):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # If parsing fails, keep as None or original value
                    value = None
        # Ensure int fields are integers
        elif model_key in ("max_tokens", "input_tokens", "output_tokens"):
            if value is not None:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    value = None
        # Ensure float fields are floats
        elif model_key == "top_p":
            if value is not None:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = None

        result[model_key] = value

    return result


def extract_trace_data(traces_dict: dict) -> dict | None:
    """
    Extract trace_id and span data from protobuf dict structure.

    Returns dict with:
    - trace_id: hex string (32 chars)
    - resource_attributes: parsed resource attributes
    - spans: list of span data dicts ready for Span model creation
    """
    resource_spans = traces_dict.get("resource_spans", [])

    if not resource_spans:
        return None

    all_spans = []
    resource_attributes = {}
    trace_id = None

    # Navigate through resource_spans -> scope_spans -> spans
    for resource_span in resource_spans:
        # Extract resource attributes for metadata
        resource = resource_span.get("resource", {})
        resource_attrs = resource.get("attributes", [])
        if resource_attrs:
            resource_attributes = parse_attributes(resource_attrs)

        # Get scope_spans
        scope_spans = resource_span.get("scope_spans", [])
        for scope_span in scope_spans:
            spans = scope_span.get("spans", [])

            for span in spans:
                # Extract trace_id from first span (all spans share same trace_id)
                if trace_id is None:
                    trace_id_b64 = span.get("trace_id")
                    if trace_id_b64:
                        try:
                            trace_id_bytes = base64.b64decode(trace_id_b64)
                            trace_id = trace_id_bytes.hex()
                        except Exception:
                            # If decoding fails, try using as-is or skip
                            trace_id = trace_id_b64

                # Decode span_id from base64
                span_id_b64 = span.get("span_id")
                span_id = None
                if span_id_b64:
                    try:
                        span_id_bytes = base64.b64decode(span_id_b64)
                        span_id = span_id_bytes.hex()
                    except Exception:
                        span_id = span_id_b64

                # Extract basic span fields
                name = span.get("name", "")

                # Convert timestamps
                start_time = None
                end_time = None
                start_nano = span.get("start_time_unix_nano")
                end_nano = span.get("end_time_unix_nano")

                if start_nano:
                    try:
                        start_time = convert_nano_to_datetime(int(start_nano))
                    except (ValueError, TypeError):
                        pass

                if end_nano:
                    try:
                        end_time = convert_nano_to_datetime(int(end_nano))
                    except (ValueError, TypeError):
                        pass

                # Parse attributes and extract gen_ai fields
                span_attributes = span.get("attributes", [])
                parsed_attrs = parse_attributes(span_attributes)
                gen_ai_fields = extract_gen_ai_fields(parsed_attrs)

                # Build span data dict
                span_data = {
                    "span_id": span_id,
                    "name": name,
                    "start_time": start_time,
                    "end_time": end_time,
                    **gen_ai_fields,  # Merge gen_ai fields
                }

                all_spans.append(span_data)

    if trace_id is None:
        return None

    return {
        "trace_id": trace_id,
        "resource_attributes": resource_attributes,
        "spans": all_spans,
    }
