import json
import os
from datetime import datetime
from django.test import TestCase
from django.utils import timezone
from traces.utils import convert_nano_to_datetime


class UtilsTestCase(TestCase):
    def setUp(self):
        test_dir = os.path.dirname(os.path.abspath(__file__))
        sample_trace_path = os.path.join(test_dir, "sample_trace.json")
        with open(sample_trace_path, "r") as f:
            self.sample_trace = json.load(f)

    def test_convert_nano_to_datetime(self):
        nano_timestamp = 1704067200000000000
        result = convert_nano_to_datetime(nano_timestamp)
        expected = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.UTC)

        self.assertIsInstance(result, datetime)
        self.assertEqual(result.tzinfo, timezone.UTC)
        self.assertEqual(result, expected)

