from datetime import datetime
from django.utils import timezone


def convert_nano_to_datetime(nano_timestamp: int) -> datetime:
    return datetime.fromtimestamp(nano_timestamp / 1e9, timezone.UTC)
