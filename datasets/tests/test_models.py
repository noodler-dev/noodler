from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
from accounts.models import Organization
from projects.models import Project
from traces.models import Trace
from datasets.models import Dataset, Annotation, FailureMode


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

    def test_annotation_get_failure_modes(self):
        """Test that get_failure_modes returns associated failure modes."""
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Test notes"
        )

        # Create failure modes
        failure_mode1 = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="False info"
        )
        failure_mode2 = FailureMode.objects.create(
            project=self.project, name="Format Error", description="Wrong format"
        )

        # Initially no failure modes
        self.assertEqual(annotation.get_failure_modes().count(), 0)

        # Add failure modes
        annotation.failure_modes.add(failure_mode1, failure_mode2)

        # Should return both
        failure_modes = annotation.get_failure_modes()
        self.assertEqual(failure_modes.count(), 2)
        self.assertIn(failure_mode1, failure_modes)
        self.assertIn(failure_mode2, failure_modes)

    def test_annotation_failure_modes_relationship(self):
        """Test that annotation can have multiple failure modes."""
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Test notes"
        )

        failure_mode1 = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="False info"
        )
        failure_mode2 = FailureMode.objects.create(
            project=self.project, name="Format Error", description="Wrong format"
        )

        annotation.failure_modes.add(failure_mode1)
        annotation.failure_modes.add(failure_mode2)

        self.assertEqual(annotation.failure_modes.count(), 2)
        self.assertIn(failure_mode1, annotation.failure_modes.all())
        self.assertIn(failure_mode2, annotation.failure_modes.all())

    def test_annotation_failure_modes_can_be_empty(self):
        """Test that annotation can have no failure modes."""
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Test notes"
        )

        self.assertEqual(annotation.failure_modes.count(), 0)
        self.assertEqual(annotation.get_failure_modes().count(), 0)

    def test_annotation_failure_modes_reverse_relationship(self):
        """Test that failure mode can access annotations via reverse relationship."""
        annotation1 = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Notes 1"
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
            trace=trace2, dataset=self.dataset, notes="Notes 2"
        )

        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="False info"
        )

        annotation1.failure_modes.add(failure_mode)
        annotation2.failure_modes.add(failure_mode)

        # Check reverse relationship
        annotations = failure_mode.annotations.all()
        self.assertEqual(annotations.count(), 2)
        self.assertIn(annotation1, annotations)
        self.assertIn(annotation2, annotations)


class FailureModeModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org")
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )

        # Create another project for testing cross-project scenarios
        self.org2 = Organization.objects.create(name="Test Org 2")
        self.project2 = Project.objects.create(
            name="Test Project 2", organization=self.org2
        )

    def test_failure_mode_creation(self):
        """Test that failure mode can be created."""
        failure_mode = FailureMode.objects.create(
            project=self.project,
            name="Hallucination",
            description="AI generated false information",
        )

        self.assertIsNotNone(failure_mode.uid)
        self.assertEqual(failure_mode.name, "Hallucination")
        self.assertEqual(failure_mode.description, "AI generated false information")
        self.assertEqual(failure_mode.project, self.project)
        self.assertIsNotNone(failure_mode.created_at)
        self.assertIsNotNone(failure_mode.updated_at)

    def test_failure_mode_str(self):
        """Test that FailureMode __str__ returns the name."""
        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )
        self.assertEqual(str(failure_mode), "Hallucination")

    def test_failure_mode_unique_constraint_per_project(self):
        """Test that unique constraint prevents duplicate names within same project."""
        FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )

        # Try to create another with same name in same project
        with self.assertRaises(IntegrityError):
            FailureMode.objects.create(
                project=self.project, name="Hallucination", description="Different"
            )

    def test_failure_mode_same_name_different_projects(self):
        """Test that same name is allowed in different projects."""
        FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )

        # Should be able to create same name in different project
        failure_mode2 = FailureMode.objects.create(
            project=self.project2, name="Hallucination", description="Test"
        )

        self.assertIsNotNone(failure_mode2)
        self.assertEqual(failure_mode2.name, "Hallucination")
        self.assertEqual(failure_mode2.project, self.project2)

    def test_failure_mode_belongs_to_project(self):
        """Test that belongs_to_project correctly identifies project ownership."""
        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )

        self.assertTrue(failure_mode.belongs_to_project(self.project))
        self.assertFalse(failure_mode.belongs_to_project(self.project2))

    def test_failure_mode_ordering(self):
        """Test that failure modes are ordered by name."""
        failure_mode_c = FailureMode.objects.create(
            project=self.project, name="C Category", description="Test"
        )
        failure_mode_a = FailureMode.objects.create(
            project=self.project, name="A Category", description="Test"
        )
        failure_mode_b = FailureMode.objects.create(
            project=self.project, name="B Category", description="Test"
        )

        failure_modes = list(FailureMode.objects.filter(project=self.project))
        # Should be ordered by name (alphabetically)
        self.assertEqual(failure_modes[0], failure_mode_a)
        self.assertEqual(failure_modes[1], failure_mode_b)
        self.assertEqual(failure_modes[2], failure_mode_c)

    def test_failure_mode_empty_description(self):
        """Test that failure mode can have empty description."""
        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description=""
        )

        self.assertEqual(failure_mode.description, "")
        self.assertIsNotNone(failure_mode.uid)

    def test_failure_mode_project_cascade_delete(self):
        """Test that failure modes are deleted when project is deleted."""
        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )
        failure_mode_id = failure_mode.id

        # Delete project
        self.project.delete()

        # Failure mode should be deleted
        self.assertFalse(FailureMode.objects.filter(id=failure_mode_id).exists())

    def test_failure_mode_reverse_relationship(self):
        """Test that project can access failure modes via reverse relationship."""
        failure_mode1 = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )
        failure_mode2 = FailureMode.objects.create(
            project=self.project, name="Format Error", description="Test"
        )

        # Check reverse relationship
        failure_modes = self.project.failure_modes.all()
        self.assertEqual(failure_modes.count(), 2)
        self.assertIn(failure_mode1, failure_modes)
        self.assertIn(failure_mode2, failure_modes)

    def test_failure_mode_annotations_relationship(self):
        """Test that failure mode can have multiple annotations."""
        dataset = Dataset.objects.create(name="Test Dataset", project=self.project)
        trace1 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        trace2 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-2",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        dataset.traces.add(trace1, trace2)

        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )

        annotation1 = Annotation.objects.create(
            trace=trace1, dataset=dataset, notes="Notes 1"
        )
        annotation2 = Annotation.objects.create(
            trace=trace2, dataset=dataset, notes="Notes 2"
        )

        annotation1.failure_modes.add(failure_mode)
        annotation2.failure_modes.add(failure_mode)

        # Check reverse relationship
        annotations = failure_mode.annotations.all()
        self.assertEqual(annotations.count(), 2)
        self.assertIn(annotation1, annotations)
        self.assertIn(annotation2, annotations)

    def test_failure_mode_uid_is_unique(self):
        """Test that failure mode uid is unique."""
        failure_mode1 = FailureMode.objects.create(
            project=self.project, name="Category 1", description="Test"
        )
        failure_mode2 = FailureMode.objects.create(
            project=self.project, name="Category 2", description="Test"
        )

        self.assertNotEqual(failure_mode1.uid, failure_mode2.uid)
        self.assertIsNotNone(failure_mode1.uid)
        self.assertIsNotNone(failure_mode2.uid)

    def test_failure_mode_timestamps(self):
        """Test that created_at and updated_at are set correctly."""
        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )

        self.assertIsNotNone(failure_mode.created_at)
        self.assertIsNotNone(failure_mode.updated_at)
        self.assertLessEqual(failure_mode.created_at, timezone.now())
        self.assertLessEqual(failure_mode.updated_at, timezone.now())

    def test_failure_mode_updated_at_changes_on_update(self):
        """Test that updated_at changes when failure mode is updated."""
        failure_mode = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="Test"
        )
        original_updated_at = failure_mode.updated_at

        # Wait a tiny bit and update
        import time

        time.sleep(0.01)

        failure_mode.description = "Updated description"
        failure_mode.save()

        failure_mode.refresh_from_db()
        self.assertGreater(failure_mode.updated_at, original_updated_at)
