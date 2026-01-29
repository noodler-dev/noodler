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

    def get_first_unannotated_trace(self):
        """Get the first trace in this dataset that hasn't been annotated yet."""
        annotated_trace_ids = Annotation.objects.filter(dataset=self).values_list(
            "trace_id", flat=True
        )
        return self.get_traces_ordered().exclude(id__in=annotated_trace_ids).first()

    def get_first_trace(self):
        """Get the first trace in this dataset (for review mode when all are annotated)."""
        return self.get_traces_ordered().first()

    def get_unannotated_count(self):
        """Return the number of traces that haven't been annotated yet."""
        annotated_trace_ids = Annotation.objects.filter(dataset=self).values_list(
            "trace_id", flat=True
        )
        return self.traces.exclude(id__in=annotated_trace_ids).count()

    def contains_trace(self, trace):
        """Check if a trace belongs to this dataset."""
        return self.traces.filter(uid=trace.uid).exists()

    def is_all_annotated(self):
        """Check if all traces in this dataset have been annotated."""
        annotated_count = Annotation.objects.filter(dataset=self).count()
        return annotated_count == self.trace_count

    def get_annotation_navigation(self, trace):
        """
        Get navigation information for annotating a trace.

        Returns a dict with:
        - prev_trace_uid: UID of previous trace (None if first)
        - next_trace_uid: UID of next trace (None if last)
        - all_annotated: Whether all traces are annotated (review mode)
        """
        all_traces = list(self.get_traces_ordered())
        annotated_trace_ids = set(
            Annotation.objects.filter(dataset=self).values_list("trace_id", flat=True)
        )
        all_annotated = len(annotated_trace_ids) == len(all_traces)

        # Find current trace index
        try:
            current_index = next(
                i for i, t in enumerate(all_traces) if t.uid == trace.uid
            )
        except StopIteration:
            return None

        # Previous: go to previous trace (even if annotated, so users can review)
        prev_trace_uid = (
            all_traces[current_index - 1].uid if current_index > 0 else None
        )

        # Next: behavior depends on whether all traces are annotated
        if all_annotated:
            # Review mode: go to next trace in order
            next_trace_uid = (
                all_traces[current_index + 1].uid
                if current_index < len(all_traces) - 1
                else None
            )
        else:
            # Annotation mode: skip to next unannotated trace
            next_unannotated_trace = None
            for t in all_traces[current_index + 1 :]:
                if t.id not in annotated_trace_ids:
                    next_unannotated_trace = t
                    break
            next_trace_uid = (
                next_unannotated_trace.uid if next_unannotated_trace else None
            )

        return {
            "prev_trace_uid": prev_trace_uid,
            "next_trace_uid": next_trace_uid,
            "all_annotated": all_annotated,
        }

    def get_annotation_progress(self, trace):
        """
        Get progress information for annotating a trace.

        Returns a dict with:
        - current_trace_number: 1-based position in all traces
        - total_traces: Total number of traces
        - annotated_count: Number of annotated traces
        - unannotated_count: Number of unannotated traces
        - current_unannotated_number: Position among unannotated traces (None if trace is annotated)
        """
        all_traces = list(self.get_traces_ordered())
        annotated_trace_ids = set(
            Annotation.objects.filter(dataset=self).values_list("trace_id", flat=True)
        )

        # Find current trace index
        try:
            current_index = next(
                i for i, t in enumerate(all_traces) if t.uid == trace.uid
            )
        except StopIteration:
            return None

        total_traces = len(all_traces)
        annotated_count = len(annotated_trace_ids)
        unannotated_count = self.get_unannotated_count()

        # Calculate position among unannotated traces
        unannotated_traces = [t for t in all_traces if t.id not in annotated_trace_ids]
        try:
            current_unannotated_index = next(
                i for i, t in enumerate(unannotated_traces) if t.uid == trace.uid
            )
            current_unannotated_number = current_unannotated_index + 1
        except StopIteration:
            # Current trace is already annotated
            current_unannotated_number = None

        return {
            "current_trace_number": current_index + 1,
            "total_traces": total_traces,
            "annotated_count": annotated_count,
            "unannotated_count": unannotated_count,
            "current_unannotated_number": current_unannotated_number,
        }

    class Meta:
        ordering = ["-created_at"]


class Annotation(models.Model):
    """Annotation for a trace within a dataset context."""

    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    trace = models.ForeignKey(
        Trace, on_delete=models.CASCADE, related_name="annotations"
    )
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name="annotations"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Annotation for {self.trace.otel_trace_id} in {self.dataset.name}"

    @classmethod
    def get_for_trace_dataset(cls, trace, dataset):
        """Get annotation for a trace-dataset pair if it exists."""
        try:
            return cls.objects.get(trace=trace, dataset=dataset)
        except cls.DoesNotExist:
            return None

    @classmethod
    def save_notes(cls, trace, dataset, notes):
        """
        Save or update annotation notes for a trace-dataset pair.

        Returns the annotation instance.
        """
        notes = notes.strip() if notes else ""
        annotation, created = cls.objects.get_or_create(
            trace=trace, dataset=dataset, defaults={"notes": notes}
        )

        if not created:
            annotation.notes = notes
            annotation.save()

        return annotation

    class Meta:
        unique_together = [["trace", "dataset"]]
        ordering = ["-created_at"]
