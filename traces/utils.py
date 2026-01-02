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
        # Fallback: return None or the value_dict itself
        return None


def parse_attributes(attributes: list) -> dict:
    result = {}

    if not attributes:
        return result

    for attr in attributes:
        key = attr.get("key")
        value = extract_attribute_value(attr)
        if key:
            result[key] = value

    return result
