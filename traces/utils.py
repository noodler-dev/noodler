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
