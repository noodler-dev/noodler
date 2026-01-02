from django.db import models
from django.db.models import JSONField, BinaryField
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


class Trace(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    trace_id = models.CharField(max_length=32)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    metadata = JSONField()

    def __str__(self):
        return self.trace_id


class Span(models.Model):
    name = models.CharField(max_length=255)
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE)
    span_id = models.CharField(max_length=16)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    provider_name = models.CharField(max_length=255, null=True, blank=True)
    operation_name = models.CharField(max_length=255, null=True, blank=True)
    request_model = models.CharField(max_length=255, null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)
    top_p = models.FloatField(null=True, blank=True)
    response_id = models.CharField(max_length=255, null=True, blank=True)
    response_model = models.CharField(max_length=255, null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    input_tokens = models.IntegerField(null=True, blank=True)
    finished_reasons = models.JSONField(null=True, blank=True)
    input_messages = models.JSONField(null=True, blank=True)
    output_messages = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name
