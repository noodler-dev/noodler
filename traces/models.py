from django.db import models
from django.db.models import JSONField
from projects.models import Project


class RawTrace(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    received_at = models.DateTimeField()
    payload = JSONField()

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
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE)
    span_id = models.CharField(max_length=16)
    parent_span_id = models.CharField(max_length=16, null=True, blank=True)
    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    attributes = JSONField()

    def __str__(self):
        return self.name
