import uuid
from django.db import models
from projects.models import Project
from traces.models import Trace


class Dataset(models.Model):
    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    traces = models.ManyToManyField(Trace, related_name="datasets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def trace_count(self):
        """Return the number of traces in this dataset."""
        return self.traces.count()

    def get_traces_ordered(self, order_by="-started_at"):
        """Get traces ordered by the specified field."""
        return self.traces.all().order_by(order_by)

    def belongs_to_project(self, project):
        """Check if this dataset belongs to the given project."""
        return self.project == project

    class Meta:
        ordering = ["-created_at"]


class Annotation(models.Model):
    """Annotation for a trace within a dataset context."""

    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE, related_name="annotations")
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="annotations")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Annotation for {self.trace.otel_trace_id} in {self.dataset.name}"

    class Meta:
        unique_together = [["trace", "dataset"]]
        ordering = ["-created_at"]
