from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from accounts.models import Organization
from projects.models import Project
from traces.models import Trace
from datasets.models import Dataset, Annotation


class DatasetModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org")
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

        # Create traces with different timestamps (ordered by -started_at, newest first)
        base_time = timezone.now()
        self.trace1 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=base_time,
            ended_at=base_time,
            attributes={},
        )
        self.trace2 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-2",
            started_at=base_time - timedelta(seconds=1),
            ended_at=base_time - timedelta(seconds=1),
            attributes={},
        )
        self.trace3 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-3",
            started_at=base_time - timedelta(seconds=2),
            ended_at=base_time - timedelta(seconds=2),
            attributes={},
        )

        self.dataset.traces.add(self.trace1, self.trace2, self.trace3)

    def test_trace_count_property(self):
        """Test that trace_count property returns correct count."""
        self.assertEqual(self.dataset.trace_count, 3)

    def test_get_traces_ordered(self):
        """Test that get_traces_ordered returns traces in correct order."""
        traces = list(self.dataset.get_traces_ordered())
        # Should be ordered by -started_at (newest first)
        self.assertEqual(traces[0], self.trace1)
        self.assertEqual(traces[1], self.trace2)
        self.assertEqual(traces[2], self.trace3)

    def test_belongs_to_project(self):
        """Test that belongs_to_project correctly identifies project ownership."""
        self.assertTrue(self.dataset.belongs_to_project(self.project))

        other_project = Project.objects.create(
            name="Other Project", organization=self.org
        )
        self.assertFalse(self.dataset.belongs_to_project(other_project))

    def test_contains_trace(self):
        """Test that contains_trace correctly identifies trace membership."""
        self.assertTrue(self.dataset.contains_trace(self.trace1))
        self.assertTrue(self.dataset.contains_trace(self.trace2))
        self.assertTrue(self.dataset.contains_trace(self.trace3))

        other_trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="other-trace",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.assertFalse(self.dataset.contains_trace(other_trace))

    def test_get_unannotated_count(self):
        """Test that get_unannotated_count returns correct count."""
        self.assertEqual(self.dataset.get_unannotated_count(), 3)

        # Annotate one trace
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Notes"
        )
        self.assertEqual(self.dataset.get_unannotated_count(), 2)

        # Annotate all traces
        Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Notes"
        )
        Annotation.objects.create(
            trace=self.trace3, dataset=self.dataset, notes="Notes"
        )
        self.assertEqual(self.dataset.get_unannotated_count(), 0)

    def test_is_all_annotated(self):
        """Test that is_all_annotated correctly identifies completion status."""
        self.assertFalse(self.dataset.is_all_annotated())

        # Annotate all traces
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Notes"
        )
        Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Notes"
        )
        Annotation.objects.create(
            trace=self.trace3, dataset=self.dataset, notes="Notes"
        )
        self.assertTrue(self.dataset.is_all_annotated())

    def test_get_first_unannotated_trace(self):
        """Test that get_first_unannotated_trace returns first unannotated trace."""
        # Should return trace1 (first in order)
        first_unannotated = self.dataset.get_first_unannotated_trace()
        self.assertEqual(first_unannotated, self.trace1)

        # Annotate trace1, should return trace2
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Notes"
        )
        first_unannotated = self.dataset.get_first_unannotated_trace()
        self.assertEqual(first_unannotated, self.trace2)

        # Annotate all, should return None
        Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Notes"
        )
        Annotation.objects.create(
            trace=self.trace3, dataset=self.dataset, notes="Notes"
        )
        first_unannotated = self.dataset.get_first_unannotated_trace()
        self.assertIsNone(first_unannotated)

    def test_get_first_trace(self):
        """Test that get_first_trace returns first trace in order."""
        first_trace = self.dataset.get_first_trace()
        self.assertEqual(first_trace, self.trace1)

    def test_get_annotation_navigation_first_trace(self):
        """Test navigation for first trace."""
        navigation = self.dataset.get_annotation_navigation(self.trace1)

        self.assertIsNotNone(navigation)
        self.assertIsNone(navigation["prev_trace_uid"])
        self.assertEqual(navigation["next_trace_uid"], self.trace2.uid)
        self.assertFalse(navigation["all_annotated"])

    def test_get_annotation_navigation_middle_trace(self):
        """Test navigation for middle trace."""
        navigation = self.dataset.get_annotation_navigation(self.trace2)

        self.assertIsNotNone(navigation)
        self.assertEqual(navigation["prev_trace_uid"], self.trace1.uid)
        self.assertEqual(navigation["next_trace_uid"], self.trace3.uid)
        self.assertFalse(navigation["all_annotated"])

    def test_get_annotation_navigation_last_trace(self):
        """Test navigation for last trace."""
        navigation = self.dataset.get_annotation_navigation(self.trace3)

        self.assertIsNotNone(navigation)
        self.assertEqual(navigation["prev_trace_uid"], self.trace2.uid)
        # If there are unannotated traces, should find the first one (trace1)
        # Only None if all traces are annotated
        self.assertEqual(navigation["next_trace_uid"], self.trace1.uid)
        self.assertFalse(navigation["all_annotated"])

    def test_get_annotation_navigation_skips_annotated(self):
        """Test that navigation skips annotated traces in annotation mode."""
        # Annotate trace2
        Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Notes"
        )

        # From trace1, should skip trace2 and go to trace3
        navigation = self.dataset.get_annotation_navigation(self.trace1)
        self.assertEqual(navigation["next_trace_uid"], self.trace3.uid)

    def test_get_annotation_navigation_finds_unannotated_backward(self):
        """Test that navigation finds unannotated traces backward when user navigates to later trace."""
        # Annotate trace3 (last trace)
        Annotation.objects.create(
            trace=self.trace3, dataset=self.dataset, notes="Notes"
        )

        # If user navigates directly to trace3 (via URL/bookmark), and trace1/trace2 are unannotated,
        # should find trace1 (first unannotated) as next, not None
        navigation = self.dataset.get_annotation_navigation(self.trace3)
        self.assertIsNotNone(navigation["next_trace_uid"])
        # Should find trace1 (first unannotated in order)
        self.assertEqual(navigation["next_trace_uid"], self.trace1.uid)
        self.assertFalse(navigation["all_annotated"])

    def test_get_annotation_navigation_review_mode(self):
        """Test that navigation goes through all traces in review mode."""
        # Annotate all traces
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Notes"
        )
        Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Notes"
        )
        Annotation.objects.create(
            trace=self.trace3, dataset=self.dataset, notes="Notes"
        )

        # In review mode, should go to next trace in order (not skip)
        navigation = self.dataset.get_annotation_navigation(self.trace1)
        self.assertTrue(navigation["all_annotated"])
        self.assertEqual(navigation["next_trace_uid"], self.trace2.uid)

        # When on last trace in review mode, next should be None
        navigation = self.dataset.get_annotation_navigation(self.trace3)
        self.assertTrue(navigation["all_annotated"])
        self.assertIsNone(navigation["next_trace_uid"])

    def test_get_annotation_navigation_trace_not_in_dataset(self):
        """Test that navigation returns None for trace not in dataset."""
        other_trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="other-trace",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        navigation = self.dataset.get_annotation_navigation(other_trace)
        self.assertIsNone(navigation)

    def test_get_annotation_progress_first_trace(self):
        """Test progress calculation for first trace."""
        progress = self.dataset.get_annotation_progress(self.trace1)

        self.assertIsNotNone(progress)
        self.assertEqual(progress["current_trace_number"], 1)
        self.assertEqual(progress["total_traces"], 3)
        self.assertEqual(progress["annotated_count"], 0)
        self.assertEqual(progress["unannotated_count"], 3)
        self.assertEqual(progress["current_unannotated_number"], 1)

    def test_get_annotation_progress_middle_trace(self):
        """Test progress calculation for middle trace."""
        progress = self.dataset.get_annotation_progress(self.trace2)

        self.assertIsNotNone(progress)
        self.assertEqual(progress["current_trace_number"], 2)
        self.assertEqual(progress["total_traces"], 3)
        self.assertEqual(progress["annotated_count"], 0)
        self.assertEqual(progress["unannotated_count"], 3)
        self.assertEqual(progress["current_unannotated_number"], 2)

    def test_get_annotation_progress_with_annotations(self):
        """Test progress calculation when some traces are annotated."""
        # Annotate trace1
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Notes"
        )

        # Check progress for trace2 (unannotated)
        progress = self.dataset.get_annotation_progress(self.trace2)
        self.assertEqual(progress["annotated_count"], 1)
        self.assertEqual(progress["unannotated_count"], 2)
        self.assertEqual(progress["current_unannotated_number"], 1)  # First unannotated

        # Check progress for trace1 (annotated)
        progress = self.dataset.get_annotation_progress(self.trace1)
        self.assertEqual(progress["annotated_count"], 1)
        self.assertEqual(progress["unannotated_count"], 2)
        self.assertIsNone(progress["current_unannotated_number"])  # Already annotated

    def test_get_annotation_progress_trace_not_in_dataset(self):
        """Test that progress returns None for trace not in dataset."""
        other_trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="other-trace",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        progress = self.dataset.get_annotation_progress(other_trace)
        self.assertIsNone(progress)


class AnnotationModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org")
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)
        self.trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.dataset.traces.add(self.trace)

    def test_annotation_str(self):
        """Test that Annotation __str__ returns correct format."""
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Test notes"
        )
        str_repr = str(annotation)
        self.assertIn("trace-1", str_repr)
        self.assertIn("Test Dataset", str_repr)

    def test_annotation_unique_constraint(self):
        """Test that unique constraint prevents duplicate annotations."""
        Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="First notes"
        )

        # Try to create another annotation for same trace-dataset pair
        # Should raise IntegrityError or use get_or_create
        annotation, created = Annotation.objects.get_or_create(
            trace=self.trace, dataset=self.dataset, defaults={"notes": "Second notes"}
        )
        self.assertFalse(created)
        self.assertEqual(annotation.notes, "First notes")

    def test_get_for_trace_dataset_existing(self):
        """Test that get_for_trace_dataset returns existing annotation."""
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Test notes"
        )

        result = Annotation.get_for_trace_dataset(self.trace, self.dataset)
        self.assertEqual(result, annotation)
        self.assertEqual(result.notes, "Test notes")

    def test_get_for_trace_dataset_nonexistent(self):
        """Test that get_for_trace_dataset returns None when annotation doesn't exist."""
        result = Annotation.get_for_trace_dataset(self.trace, self.dataset)
        self.assertIsNone(result)

    def test_save_notes_creates_new(self):
        """Test that save_notes creates new annotation."""
        annotation = Annotation.save_notes(self.trace, self.dataset, "New notes")

        self.assertIsNotNone(annotation)
        self.assertEqual(annotation.notes, "New notes")
        self.assertEqual(annotation.trace, self.trace)
        self.assertEqual(annotation.dataset, self.dataset)

    def test_save_notes_updates_existing(self):
        """Test that save_notes updates existing annotation."""
        Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Old notes"
        )

        annotation = Annotation.save_notes(self.trace, self.dataset, "New notes")
        self.assertEqual(annotation.notes, "New notes")

        # Verify only one annotation exists
        self.assertEqual(
            Annotation.objects.filter(trace=self.trace, dataset=self.dataset).count(), 1
        )

    def test_save_notes_empty_string(self):
        """Test that save_notes handles empty string."""
        annotation = Annotation.save_notes(self.trace, self.dataset, "")
        self.assertEqual(annotation.notes, "")

    def test_save_notes_strips_whitespace(self):
        """Test that save_notes strips whitespace."""
        annotation = Annotation.save_notes(
            self.trace, self.dataset, "  Notes with spaces  "
        )
        self.assertEqual(annotation.notes, "Notes with spaces")

    def test_save_notes_none(self):
        """Test that save_notes handles None."""
        annotation = Annotation.save_notes(self.trace, self.dataset, None)
        self.assertEqual(annotation.notes, "")

    def test_annotation_ordering(self):
        """Test that annotations are ordered by created_at descending."""
        annotation1 = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="First"
        )

        # Create another trace and annotation
        trace2 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-2",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.dataset.traces.add(trace2)
        annotation2 = Annotation.objects.create(
            trace=trace2, dataset=self.dataset, notes="Second"
        )

        annotations = list(Annotation.objects.filter(dataset=self.dataset))
        # Should be ordered by -created_at (newest first)
        self.assertEqual(annotations[0], annotation2)
        self.assertEqual(annotations[1], annotation1)
