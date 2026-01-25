import uuid
from django.db import models, transaction
from django.db.models import JSONField, BinaryField
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.trace.v1.trace_pb2 import TracesData

from projects.models import Project
from traces.utils import extract_trace_data


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

    @transaction.atomic
    def process(self):
        """
        Main processing method: converts protobuf to Trace and Span objects.

        Returns the created/updated Trace object, or None on error.
        """
        try:
            # Step 1: Convert protobuf to dict
            traces_dict = self.convert_to_dict()

            # Step 2: Extract trace data
            extracted_data = extract_trace_data(traces_dict)

            if not extracted_data:
                self.status = "error"
                self.save(update_fields=["status"])
                return None

            # Step 3: Create Trace and Spans
            trace = self._create_trace_and_spans(extracted_data)

            if trace:
                # Step 4: Update status to processed
                self.status = "processed"
                self.save(update_fields=["status"])
                return trace
            else:
                self.status = "error"
                self.save(update_fields=["status"])
                return None

        except Exception:
            # On any error, mark as error and re-raise
            self.status = "error"
            self.save(update_fields=["status"])
            raise

    def _create_trace_and_spans(self, extracted_data):
        """
        Create Trace and Span objects from extracted data.

        Returns the created/updated Trace object.
        """
        if not extracted_data:
            return None

        trace_id = extracted_data["trace_id"]
        resource_attributes = extracted_data.get("resource_attributes", {})
        spans_data = extracted_data.get("spans", [])

        if not spans_data:
            return None

        # Try to autopopulate Trace.service_name from OTel resource attributes.
        # Example: {"service.name": "noodler-service", ...}
        service_name = resource_attributes.get("service.name")
        if not isinstance(service_name, str):
            service_name = None
        if service_name:
            service_name = service_name[:50]

        # Calculate trace timestamps from spans
        start_times = [s["start_time"] for s in spans_data if s.get("start_time")]
        end_times = [s["end_time"] for s in spans_data if s.get("end_time")]

        started_at = min(start_times) if start_times else None
        ended_at = max(end_times) if end_times else None

        # If no valid timestamps, use received_at as fallback
        if not started_at:
            started_at = self.received_at
        if not ended_at:
            ended_at = self.received_at

        # Create or get Trace
        trace, created = Trace.objects.get_or_create(
            otel_trace_id=trace_id,
            project=self.project,
            defaults={
                "started_at": started_at,
                "ended_at": ended_at,
                "service_name": service_name,
                "attributes": resource_attributes,
            },
        )

        # Update trace if it already existed (in case timestamps changed)
        if not created:
            trace.started_at = started_at
            trace.ended_at = ended_at
            if service_name:
                trace.service_name = service_name
            trace.attributes = resource_attributes
            trace.save()

        # Prepare Span objects for bulk_create
        span_objects = []
        for span_data in spans_data:
            span = Span(
                trace=trace,
                otel_span_id=span_data.get("span_id", ""),
                name=span_data.get("name", ""),
                start_time=span_data.get("start_time") or started_at,
                end_time=span_data.get("end_time"),
                provider_name=span_data.get("provider_name"),
                operation_name=span_data.get("operation_name"),
                request_model=span_data.get("request_model"),
                max_tokens=span_data.get("max_tokens"),
                top_p=span_data.get("top_p"),
                response_id=span_data.get("response_id"),
                response_model=span_data.get("response_model"),
                output_tokens=span_data.get("output_tokens"),
                input_tokens=span_data.get("input_tokens"),
                finished_reasons=span_data.get("finished_reasons"),
                system_instructions=span_data.get("system_instructions"),
                input_messages=span_data.get("input_messages"),
                output_messages=span_data.get("output_messages"),
            )
            span_objects.append(span)

        # Bulk create spans
        if span_objects:
            Span.objects.bulk_create(span_objects, ignore_conflicts=True)

        return trace


class Trace(models.Model):
    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    otel_trace_id = models.CharField(max_length=32)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    service_name = models.CharField(max_length=50, null=True, blank=True)
    attributes = JSONField()

    def __str__(self):
        return self.otel_trace_id


class Span(models.Model):
    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    name = models.CharField(max_length=50)
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE)
    otel_span_id = models.CharField(max_length=16)
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
    system_instructions = models.JSONField(
        null=True,
        blank=True,
        help_text="This is different from the system prompt, some providers allow instructions to be sent separately from the chat history.",
    )
    input_messages = models.JSONField(null=True, blank=True)
    output_messages = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name
