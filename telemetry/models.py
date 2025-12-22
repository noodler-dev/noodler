from django.db import models
from django.db.models import JSONField


class Trace(models.Model):
    trace_id = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.trace_id


class Observation(models.Model):
    span_id = models.CharField(max_length=16)
    trace = models.ForeignKey(
        Trace, on_delete=models.CASCADE, related_name="observations"
    )
    parent_span_id = models.CharField(max_length=16, null=True, blank=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=32)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    attributes = JSONField()
    projected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Generation(models.Model):
    observation = models.OneToOneField(
        Observation, on_delete=models.CASCADE, related_name="generation"
    )
    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=128)
    input = JSONField()
    output = JSONField(null=True, blank=True)
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.model
