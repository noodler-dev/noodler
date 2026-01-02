from django.db import models
from django.db.models import JSONField, BinaryField
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.trace.v1.trace_pb2 import TracesData

from projects.models import Project


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
        pass

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
