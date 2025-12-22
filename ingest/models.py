from django.db import models
from django.db.models import JSONField


class RawSpan(models.Model):
    trace_id = models.CharField(max_length=32)
    span_id = models.CharField(max_length=16)
    parent_span_id = models.CharField(max_length=16, null=True, blank=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=32)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    attributes = JSONField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    projected = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["trace_id", "span_id"], name="unique_raw_span"
            )
        ]
        indexes = [
            models.Index(fields=["trace_id"]),
            models.Index(fields=["ingested_at"]),
        ]
