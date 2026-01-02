import base64
from django.db import models
from django.db.models import JSONField, BinaryField
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.trace.v1.trace_pb2 import TracesData

from projects.models import Project
from traces.utils import (
    convert_nano_to_datetime,
    parse_attributes,
    extract_gen_ai_fields,
)


class RawTrace(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("error", "Error"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    payload_json = JSONField(blank=True, null=True)
    payload_protobuf = BinaryField(blank=True, null=True)
    received_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"RawTrace for {self.project.name}"

    def convert_to_dict(self):
        # Parse the protobuf message
        traces_data = TracesData()
        traces_data.ParseFromString(self.payload_protobuf)

        # Convert protobuf message to dictionary (unmarshalling)
        traces_dict = MessageToDict(traces_data, preserving_proto_field_name=True)

        return traces_dict

    def process(self):
        traces_dict = self.convert_to_dict()
        return traces_dict

    def _extract_trace_data(self, traces_dict):
        """
        Extract trace_id and span data from protobuf dict structure.

        Returns dict with:
        - trace_id: hex string (32 chars)
        - resource_metadata: parsed resource attributes
        - spans: list of span data dicts ready for Span model creation
        """
        resource_spans = traces_dict.get("resource_spans", [])

        if not resource_spans:
            return None

        all_spans = []
        resource_metadata = {}
        trace_id = None

        # Navigate through resource_spans -> scope_spans -> spans
        for resource_span in resource_spans:
            # Extract resource attributes for metadata
            resource = resource_span.get("resource", {})
            resource_attrs = resource.get("attributes", [])
            if resource_attrs:
                resource_metadata = parse_attributes(resource_attrs)

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
            "resource_metadata": resource_metadata,
            "spans": all_spans,
        }

    def _create_trace_and_spans(self, extracted_data):
        pass


class Trace(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    trace_id = models.CharField(max_length=32)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    metadata = JSONField()

    def __str__(self):
        return self.trace_id


class Span(models.Model):
    name = models.CharField(max_length=50)
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE)
    span_id = models.CharField(max_length=16)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    provider_name = models.CharField(max_length=50, null=True, blank=True)
    operation_name = models.CharField(max_length=50, null=True, blank=True)
    request_model = models.CharField(max_length=100, null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)
    top_p = models.FloatField(null=True, blank=True)
    response_id = models.CharField(max_length=100, null=True, blank=True)
    response_model = models.CharField(max_length=100, null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    input_tokens = models.IntegerField(null=True, blank=True)
    finished_reasons = models.JSONField(null=True, blank=True)
    input_messages = models.JSONField(null=True, blank=True)
    output_messages = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name
