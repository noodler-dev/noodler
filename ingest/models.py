from django.db import models
from django.db.models import JSONField
from projects.models import Project


class RawTraceOLD(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    received_at = models.DateTimeField()
    payload = JSONField()

    def __str__(self):
        return f"RawTrace for {self.project.name}"
