from django.db import models
from django.db.models import JSONField
from projects.models import Project


class Trace(models.Model):
    trace_id = models.CharField(max_length=32)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    metadata = JSONField()

    def __str__(self):
        return self.trace_id