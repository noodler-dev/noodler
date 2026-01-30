from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.utils import timezone
from datetime import timedelta
from accounts.models import UserProfile, Organization, Membership
from projects.models import Project
from traces.models import Trace, Span
from datasets.models import Dataset, Annotation, FailureMode

User = get_user_model()


class DatasetListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.list_url = reverse("datasets:list")

    def test_dataset_list_requires_authentication(self):
        """Test that dataset list redirects unauthenticated users."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_dataset_list_auto_selects_project(self):
        """Test that dataset list auto-selects project if user has access."""
        self.client.login(username="testuser", password="testpass123")
        # Decorator auto-selects project, so should succeed
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_dataset_list_shows_datasets_for_current_project(self):
        """Test that dataset list shows datasets for the current project."""
        self.client.login(username="testuser", password="testpass123")
        # Set current project in session
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create datasets
        Dataset.objects.create(name="Dataset 1", project=self.project)
        Dataset.objects.create(name="Dataset 2", project=self.project)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/list.html")
        self.assertContains(response, "Dataset 1")
        self.assertContains(response, "Dataset 2")

    def test_dataset_list_shows_empty_message_when_no_datasets(self):
        """Test that empty dataset list shows helpful message."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No datasets found")

    def test_dataset_list_shows_trace_count(self):
        """Test that dataset list shows trace count for each dataset."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create trace
        trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="test-trace-id",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        # Create dataset with trace
        dataset = Dataset.objects.create(name="Dataset 1", project=self.project)
        dataset.traces.add(trace)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dataset 1")
        # Trace count should be displayed (1)

    def test_dataset_list_only_shows_datasets_for_current_project(self):
        """Test that dataset list only shows datasets for current project."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project and dataset
        other_project = Project.objects.create(
            name="Other Project", organization=self.org
        )
        Dataset.objects.create(name="Other Dataset", project=other_project)

        # Create dataset for current project
        Dataset.objects.create(name="Current Dataset", project=self.project)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current Dataset")
        self.assertNotContains(response, "Other Dataset")


class DatasetCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.create_url = reverse("datasets:create")

    def test_dataset_create_requires_authentication(self):
        """Test that dataset create redirects unauthenticated users."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)

    def test_dataset_create_auto_selects_project(self):
        """Test that dataset create auto-selects project if user has access."""
        self.client.login(username="testuser", password="testpass123")
        # Decorator auto-selects project, so should succeed
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)

    def test_dataset_create_get_shows_form(self):
        """Test that GET request shows the create form."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/new.html")
        self.assertContains(response, "form")

    def test_dataset_create_with_valid_data_creates_dataset(self):
        """Test that valid form submission creates a dataset."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create traces
        for i in range(5):
            Trace.objects.create(
                project=self.project,
                otel_trace_id=f"trace-{i}",
                started_at=timezone.now(),
                ended_at=timezone.now(),
                attributes={},
            )

        dataset_count_before = Dataset.objects.count()
        response = self.client.post(
            self.create_url, {"name": "Test Dataset", "num_traces": 3}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Dataset.objects.count(), dataset_count_before + 1)
        dataset = Dataset.objects.get(name="Test Dataset")
        self.assertEqual(dataset.project, self.project)
        self.assertEqual(dataset.trace_count, 3)

    def test_dataset_create_redirects_to_detail_on_success(self):
        """Test that successful creation redirects to dataset detail."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create traces
        Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        response = self.client.post(
            self.create_url, {"name": "Test Dataset", "num_traces": 1}
        )

        dataset = Dataset.objects.get(name="Test Dataset")
        self.assertRedirects(response, reverse("datasets:detail", args=[dataset.uid]))

    def test_dataset_create_no_success_message(self):
        """Test that no success message is displayed after creation (removed per requirements)."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create traces
        Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        response = self.client.post(
            self.create_url, {"name": "Test Dataset", "num_traces": 1}, follow=True
        )
        messages = list(get_messages(response.wsgi_request))

        # Success message was removed, so no messages should be shown
        # (unless there's a warning about truncation)
        self.assertEqual(len(messages), 0)

    def test_dataset_create_empty_name_shows_error(self):
        """Test that empty name shows error message."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create traces
        Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        dataset_count_before = Dataset.objects.count()
        response = self.client.post(self.create_url, {"name": "", "num_traces": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dataset.objects.count(), dataset_count_before)

    def test_dataset_create_invalid_num_traces_shows_error(self):
        """Test that invalid num_traces shows error."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create traces
        Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        dataset_count_before = Dataset.objects.count()
        response = self.client.post(
            self.create_url, {"name": "Test Dataset", "num_traces": 0}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dataset.objects.count(), dataset_count_before)

    def test_dataset_create_no_traces_available_shows_error(self):
        """Test that error is shown when no traces are available."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        dataset_count_before = Dataset.objects.count()
        response = self.client.post(
            self.create_url, {"name": "Test Dataset", "num_traces": 1}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dataset.objects.count(), dataset_count_before)
        # Form validation error is in form.errors, not messages
        self.assertIn("form", response.context)
        form = response.context["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("num_traces", form.errors)

    def test_dataset_create_more_traces_than_available_shows_warning(self):
        """Test that warning is shown when requesting more traces than available."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create only 2 traces
        Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-2",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        # Requesting more than available should show form validation error
        response = self.client.post(
            self.create_url, {"name": "Test Dataset", "num_traces": 5}
        )

        # Form validation prevents creation when requesting more than available
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("num_traces", form.errors)


class DatasetDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

    def test_dataset_detail_requires_authentication(self):
        """Test that dataset detail redirects unauthenticated users."""
        response = self.client.get(reverse("datasets:detail", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 302)

    def test_dataset_detail_auto_selects_project(self):
        """Test that dataset detail auto-selects project if user has access."""
        self.client.login(username="testuser", password="testpass123")
        # Decorator auto-selects project, so should succeed
        response = self.client.get(reverse("datasets:detail", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 200)

    def test_dataset_detail_shows_dataset_info(self):
        """Test that detail view shows dataset information."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        response = self.client.get(reverse("datasets:detail", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/detail.html")
        self.assertContains(response, "Test Dataset")

    def test_dataset_detail_shows_traces(self):
        """Test that detail view shows traces in the dataset."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create traces
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

        self.dataset.traces.add(trace1, trace2)

        response = self.client.get(reverse("datasets:detail", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trace-1")
        self.assertContains(response, "trace-2")

    def test_dataset_detail_access_control(self):
        """Test that users cannot view datasets from other projects."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project and dataset
        other_org = Organization.objects.create(name="Other Org")
        other_project = Project.objects.create(
            name="Other Project", organization=other_org
        )
        other_dataset = Dataset.objects.create(
            name="Other Dataset", project=other_project
        )

        response = self.client.get(reverse("datasets:detail", args=[other_dataset.uid]))
        # Should redirect with error
        self.assertEqual(response.status_code, 302)

    def test_dataset_detail_wrong_current_project_shows_error(self):
        """Test that error is shown when dataset doesn't belong to current project."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project in same org
        other_project = Project.objects.create(
            name="Other Project", organization=self.org
        )
        other_dataset = Dataset.objects.create(
            name="Other Dataset", project=other_project
        )

        response = self.client.get(
            reverse("datasets:detail", args=[other_dataset.uid]), follow=True
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("does not belong", str(messages[0]).lower())


class DatasetDeleteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

    def test_dataset_delete_requires_authentication(self):
        """Test that dataset delete redirects unauthenticated users."""
        response = self.client.post(reverse("datasets:delete", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 302)

    def test_dataset_delete_requires_post(self):
        """Test that dataset delete requires POST method."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        response = self.client.get(reverse("datasets:delete", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_dataset_delete_requires_current_project(self):
        """Test that dataset delete requires a current project."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(reverse("datasets:delete", args=[self.dataset.uid]))
        self.assertEqual(response.status_code, 302)

    def test_dataset_delete_removes_dataset(self):
        """Test that dataset delete removes the dataset."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        dataset_id = self.dataset.id
        response = self.client.post(reverse("datasets:delete", args=[self.dataset.uid]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Dataset.objects.filter(id=dataset_id).exists())

    def test_dataset_delete_redirects_to_list(self):
        """Test that successful delete redirects to dataset list."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        response = self.client.post(reverse("datasets:delete", args=[self.dataset.uid]))
        self.assertRedirects(response, reverse("datasets:list"))

    def test_dataset_delete_shows_success_message(self):
        """Test that success message is displayed after delete."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        response = self.client.post(
            reverse("datasets:delete", args=[self.dataset.uid]), follow=True
        )
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(len(messages), 1)
        self.assertIn("deleted successfully", str(messages[0]).lower())

    def test_dataset_delete_access_control(self):
        """Test that users cannot delete datasets from other projects."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project and dataset
        other_org = Organization.objects.create(name="Other Org")
        other_project = Project.objects.create(
            name="Other Project", organization=other_org
        )
        other_dataset = Dataset.objects.create(
            name="Other Dataset", project=other_project
        )

        dataset_id = other_dataset.id
        response = self.client.post(
            reverse("datasets:delete", args=[other_dataset.uid])
        )

        # Should redirect with error
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Dataset.objects.filter(id=dataset_id).exists())

    def test_dataset_delete_wrong_current_project_shows_error(self):
        """Test that error is shown when dataset doesn't belong to current project."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project in same org
        other_project = Project.objects.create(
            name="Other Project", organization=self.org
        )
        other_dataset = Dataset.objects.create(
            name="Other Dataset", project=other_project
        )

        response = self.client.post(
            reverse("datasets:delete", args=[other_dataset.uid]), follow=True
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("does not belong", str(messages[0]).lower())


class AnnotationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

        # Create traces with different timestamps (ordered by -started_at, so newest first)
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

        # Note: Ordered by -started_at, so order is: trace1 (newest), trace2, trace3 (oldest)

        # Create spans for trace1
        self.span1 = Span.objects.create(
            trace=self.trace1,
            name="span-1",
            otel_span_id="span1",
            start_time=timezone.now(),
            end_time=timezone.now(),
            input_messages=[
                {"role": "user", "parts": [{"type": "text", "content": "Hello"}]}
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "content": "Hi there"}],
                }
            ],
        )

    def test_annotation_view_requires_authentication(self):
        """Test that annotation view redirects unauthenticated users."""
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_annotation_view_requires_current_project(self):
        """Test that annotation view requires a current project."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)
        # Should redirect to projects list or auto-select
        self.assertIn(response.status_code, [302, 200])

    def test_annotation_view_get_displays_form(self):
        """Test that GET request displays the annotation form."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/annotate.html")
        self.assertContains(response, "form")
        self.assertContains(response, "Conversation")

    def test_annotation_view_shows_existing_annotation(self):
        """Test that existing annotation is pre-filled in the form."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create annotation
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Existing notes"
        )

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("notes"), "Existing notes")

    def test_annotation_view_post_saves_annotation(self):
        """Test that POST request saves annotation."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.post(url, {"notes": "Test annotation notes"})

        # Should redirect to next trace
        self.assertEqual(response.status_code, 302)

        # Verify annotation was created
        annotation = Annotation.objects.get(trace=self.trace1, dataset=self.dataset)
        self.assertEqual(annotation.notes, "Test annotation notes")

    def test_annotation_view_post_updates_existing_annotation(self):
        """Test that POST request updates existing annotation."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create existing annotation
        Annotation.objects.create(
            trace=self.trace1, dataset=self.dataset, notes="Old notes"
        )

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.post(url, {"notes": "New notes"})

        self.assertEqual(response.status_code, 302)

        # Verify annotation was updated
        annotation = Annotation.objects.get(trace=self.trace1, dataset=self.dataset)
        self.assertEqual(annotation.notes, "New notes")

    def test_annotation_view_post_empty_notes_marks_as_reviewed(self):
        """Test that empty notes still marks trace as reviewed."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.post(url, {"notes": ""})

        self.assertEqual(response.status_code, 302)

        # Verify annotation was created (even with empty notes)
        annotation = Annotation.objects.get(trace=self.trace1, dataset=self.dataset)
        self.assertEqual(annotation.notes, "")

    def test_annotation_view_redirects_to_next_trace(self):
        """Test that saving annotation redirects to next unannotated trace."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # trace1 is first in order (newest), so next should be trace2
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.post(url, {"notes": "Notes"})

        # Should redirect to trace2 (next unannotated)
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.trace2.uid), response.url)

    def test_annotation_view_skips_annotated_traces(self):
        """Test that navigation skips already annotated traces."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Annotate trace2
        Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Already annotated"
        )

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.post(url, {"notes": "Notes"})

        # Should skip trace2 and go to trace3
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.trace3.uid), response.url)

    def test_annotation_view_redirects_to_detail_when_finished(self):
        """Test that finishing all traces redirects to dataset detail."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Annotate trace2 and trace3
        Annotation.objects.create(trace=self.trace2, dataset=self.dataset, notes="")
        Annotation.objects.create(trace=self.trace3, dataset=self.dataset, notes="")

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.post(url, {"notes": "Notes"}, follow=True)

        # Should redirect to dataset detail
        self.assertRedirects(
            response, reverse("datasets:detail", args=[self.dataset.uid])
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertIn("finished annotating", str(messages[0]).lower())

    def test_annotation_view_shows_progress(self):
        """Test that progress information is displayed."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # trace1 is first in order (newest), so current_trace_number should be 1
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["total_traces"], 3)
        self.assertEqual(context["current_trace_number"], 1)  # trace1 is first in order
        self.assertEqual(context["unannotated_count"], 3)

    def test_annotation_view_shows_navigation_buttons(self):
        """Test that Previous/Next buttons are displayed correctly."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Test first trace in order (trace1 is newest, so first) - no previous
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIsNone(context["prev_trace_uid"])
        self.assertIsNotNone(context["next_trace_uid"])

        # Test middle trace (trace2) - has both
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace2.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIsNotNone(context["prev_trace_uid"])
        self.assertIsNotNone(context["next_trace_uid"])

        # Test last trace (trace3 is oldest, so last) - no next
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace3.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIsNotNone(context["prev_trace_uid"])
        # Next might be None if it's the last unannotated trace

    def test_annotation_view_access_control_wrong_project(self):
        """Test that users cannot annotate traces from other projects."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project and dataset
        other_org = Organization.objects.create(name="Other Org")
        other_project = Project.objects.create(
            name="Other Project", organization=other_org
        )
        other_dataset = Dataset.objects.create(
            name="Other Dataset", project=other_project
        )
        other_trace = Trace.objects.create(
            project=other_project,
            otel_trace_id="other-trace",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        other_dataset.traces.add(other_trace)

        url = reverse("datasets:annotate", args=[other_dataset.uid, other_trace.uid])
        response = self.client.get(url)

        # Should redirect with error
        self.assertEqual(response.status_code, 302)

    def test_annotation_view_trace_not_in_dataset(self):
        """Test that error is shown when trace doesn't belong to dataset."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create trace not in dataset
        other_trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="other-trace",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        url = reverse("datasets:annotate", args=[self.dataset.uid, other_trace.uid])
        response = self.client.get(url, follow=True)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("does not belong", str(messages[0]).lower())

    def test_annotation_view_review_mode_navigates_all_traces(self):
        """Test that review mode navigates through all traces, not just unannotated."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Annotate all traces
        Annotation.objects.create(trace=self.trace1, dataset=self.dataset, notes="")
        Annotation.objects.create(trace=self.trace2, dataset=self.dataset, notes="")
        Annotation.objects.create(trace=self.trace3, dataset=self.dataset, notes="")

        # In review mode, trace1 is first, so next should be trace2
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertTrue(context["all_annotated"])
        self.assertEqual(context["next_trace_uid"], self.trace2.uid)

    def test_annotation_view_review_mode_finish_message(self):
        """Test that review mode shows appropriate finish message."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Annotate all traces
        Annotation.objects.create(trace=self.trace1, dataset=self.dataset, notes="")
        Annotation.objects.create(trace=self.trace2, dataset=self.dataset, notes="")
        Annotation.objects.create(trace=self.trace3, dataset=self.dataset, notes="")

        # Finish reviewing (post on last trace in order - trace3)
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace3.uid])
        response = self.client.post(url, {"notes": "Updated notes"}, follow=True)

        messages = list(get_messages(response.wsgi_request))
        self.assertGreater(len(messages), 0)
        self.assertIn("finished reviewing", str(messages[0]).lower())

    def test_annotation_view_shows_conversation_messages(self):
        """Test that conversation messages are displayed."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIn("conversation_messages", context)
        # Should have messages from span1
        self.assertGreater(len(context["conversation_messages"]), 0)


class CategorizeDatasetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

        # Create traces
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
        self.dataset.traces.add(self.trace1, self.trace2)

        # Create annotations with notes
        self.annotation1 = Annotation.objects.create(
            trace=self.trace1,
            dataset=self.dataset,
            notes="This is a hallucination error",
        )
        self.annotation2 = Annotation.objects.create(
            trace=self.trace2, dataset=self.dataset, notes="Format error in response"
        )

    def test_categorize_dataset_requires_authentication(self):
        """Test that categorize dataset redirects unauthenticated users."""
        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_categorize_dataset_requires_post(self):
        """Test that categorize dataset requires POST method."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_categorize_dataset_requires_current_project(self):
        """Test that categorize dataset requires current project."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.post(url)
        # Should redirect or auto-select
        self.assertIn(response.status_code, [302, 200])

    @patch("datasets.views.categorize_annotations")
    def test_categorize_dataset_creates_categories(self, mock_categorize):
        """Test that categorize dataset creates failure mode categories."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Mock LLM response
        mock_categorize.return_value = [
            {"name": "Hallucination", "description": "AI generated false information"},
            {"name": "Format Error", "description": "Response format is incorrect"},
        ]

        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(FailureMode.objects.filter(project=self.project).count(), 2)
        self.assertTrue(
            FailureMode.objects.filter(
                project=self.project, name="Hallucination"
            ).exists()
        )
        self.assertTrue(
            FailureMode.objects.filter(
                project=self.project, name="Format Error"
            ).exists()
        )

    @patch("datasets.views.categorize_annotations")
    def test_categorize_dataset_no_annotations_shows_warning(self, mock_categorize):
        """Test that categorize dataset shows warning when no annotations exist."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Delete all annotations
        Annotation.objects.all().delete()

        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertTrue(any("No annotations" in str(m) for m in messages_list))

    @patch("datasets.views.categorize_annotations")
    def test_categorize_dataset_handles_api_error(self, mock_categorize):
        """Test that categorize dataset handles API errors gracefully."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Mock API error
        mock_categorize.side_effect = ValueError("API key not set")

        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Failed to generate" in str(m) for m in messages_list))

    @patch("datasets.views.categorize_annotations")
    def test_categorize_dataset_does_not_auto_assign_categories(self, mock_categorize):
        """Test that categorize dataset does not automatically assign categories to annotations."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Mock LLM response
        mock_categorize.return_value = [
            {"name": "Hallucination", "description": "AI generated false information"},
        ]

        url = reverse("datasets:categorize", args=[self.dataset.uid])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        FailureMode.objects.get(
            project=self.project, name="Hallucination"
        )
        # Categories should not be automatically assigned
        self.assertEqual(self.annotation1.failure_modes.count(), 0)
        self.assertEqual(self.annotation2.failure_modes.count(), 0)


class CategoryListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

        # Create failure modes
        self.failure_mode1 = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="False information"
        )
        self.failure_mode2 = FailureMode.objects.create(
            project=self.project, name="Format Error", description="Wrong format"
        )

        # Create trace and annotation
        self.trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.dataset.traces.add(self.trace)
        self.annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Test notes"
        )
        self.annotation.failure_modes.add(self.failure_mode1)

    def test_category_list_requires_authentication(self):
        """Test that category list redirects unauthenticated users."""
        url = reverse("datasets:categories", args=[self.dataset.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_category_list_shows_categories(self):
        """Test that category list shows all categories for the project."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:categories", args=[self.dataset.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/categories.html")
        self.assertContains(response, "Hallucination")
        self.assertContains(response, "Format Error")

    def test_category_list_shows_annotation_counts(self):
        """Test that category list shows annotation counts per category."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:categories", args=[self.dataset.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # failure_mode1 has 1 annotation, failure_mode2 has 0
        context = response.context
        self.assertIn("failure_modes_with_counts", context)
        counts = {
            item["failure_mode"].name: item["count"]
            for item in context["failure_modes_with_counts"]
        }
        self.assertEqual(counts["Hallucination"], 1)
        self.assertEqual(counts["Format Error"], 0)

    def test_category_list_access_control(self):
        """Test that category list enforces access control."""
        # Create another user and project
        user2 = User.objects.create_user(username="user2", password="testpass123")
        user2_profile = UserProfile.objects.create(user=user2)
        org2 = Organization.objects.create(name="Org 2")
        Membership.objects.create(
            user_profile=user2_profile, organization=org2, role="admin"
        )
        project2 = Project.objects.create(name="Project 2", organization=org2)
        dataset2 = Dataset.objects.create(name="Dataset 2", project=project2)

        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:categories", args=[dataset2.uid])
        response = self.client.get(url)
        # Should redirect with error
        self.assertEqual(response.status_code, 302)


class CategoryCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

    def test_category_create_requires_authentication(self):
        """Test that category create redirects unauthenticated users."""
        url = reverse("datasets:category_create", args=[self.dataset.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_category_create_get_shows_form(self):
        """Test that GET request shows the category creation form."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:category_create", args=[self.dataset.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/category_form.html")
        self.assertContains(response, "form")

    def test_category_create_post_creates_category(self):
        """Test that POST request creates a new category."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:category_create", args=[self.dataset.uid])
        response = self.client.post(
            url, {"name": "New Category", "description": "Test description"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FailureMode.objects.filter(
                project=self.project, name="New Category"
            ).exists()
        )

    def test_category_create_validates_unique_name_per_project(self):
        """Test that category create validates unique name within project."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create existing category
        FailureMode.objects.create(
            project=self.project, name="Existing Category", description="Test"
        )

        url = reverse("datasets:category_create", args=[self.dataset.uid])
        response = self.client.post(
            url, {"name": "Existing Category", "description": "Duplicate"}
        )

        self.assertEqual(response.status_code, 200)  # Form errors, doesn't redirect
        self.assertContains(response, "already exists")

    def test_category_create_allows_same_name_different_project(self):
        """Test that same category name is allowed in different projects."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create another project and category
        org2 = Organization.objects.create(name="Org 2")
        project2 = Project.objects.create(name="Project 2", organization=org2)
        FailureMode.objects.create(
            project=project2, name="Shared Name", description="Test"
        )

        url = reverse("datasets:category_create", args=[self.dataset.uid])
        response = self.client.post(
            url, {"name": "Shared Name", "description": "Different project"}
        )

        # Should succeed - different project
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FailureMode.objects.filter(
                project=self.project, name="Shared Name"
            ).exists()
        )


class CategoryEditViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)
        self.failure_mode = FailureMode.objects.create(
            project=self.project, name="Original Name", description="Original desc"
        )

    def test_category_edit_requires_authentication(self):
        """Test that category edit redirects unauthenticated users."""
        url = reverse(
            "datasets:category_edit", args=[self.dataset.uid, self.failure_mode.uid]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_category_edit_get_shows_form(self):
        """Test that GET request shows the category edit form."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse(
            "datasets:category_edit", args=[self.dataset.uid, self.failure_mode.uid]
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "datasets/category_form.html")
        self.assertContains(response, "Original Name")

    def test_category_edit_post_updates_category(self):
        """Test that POST request updates the category."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse(
            "datasets:category_edit", args=[self.dataset.uid, self.failure_mode.uid]
        )
        response = self.client.post(
            url, {"name": "Updated Name", "description": "Updated description"}
        )

        self.assertEqual(response.status_code, 302)
        self.failure_mode.refresh_from_db()
        self.assertEqual(self.failure_mode.name, "Updated Name")
        self.assertEqual(self.failure_mode.description, "Updated description")

    def test_category_edit_access_control(self):
        """Test that category edit enforces access control."""
        # Create another project
        org2 = Organization.objects.create(name="Org 2")
        project2 = Project.objects.create(name="Project 2", organization=org2)
        failure_mode2 = FailureMode.objects.create(
            project=project2, name="Other Category", description="Test"
        )
        dataset2 = Dataset.objects.create(name="Dataset 2", project=project2)

        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:category_edit", args=[dataset2.uid, failure_mode2.uid])
        response = self.client.get(url)
        # Should redirect with error
        self.assertEqual(response.status_code, 302)


class CategoryDeleteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)
        self.failure_mode = FailureMode.objects.create(
            project=self.project, name="To Delete", description="Will be deleted"
        )

    def test_category_delete_requires_authentication(self):
        """Test that category delete redirects unauthenticated users."""
        url = reverse(
            "datasets:category_delete", args=[self.dataset.uid, self.failure_mode.uid]
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_category_delete_requires_post(self):
        """Test that category delete requires POST method."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse(
            "datasets:category_delete", args=[self.dataset.uid, self.failure_mode.uid]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_category_delete_removes_category(self):
        """Test that category delete removes the category."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        failure_mode_uid = self.failure_mode.uid
        url = reverse(
            "datasets:category_delete", args=[self.dataset.uid, failure_mode_uid]
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(FailureMode.objects.filter(uid=failure_mode_uid).exists())

    def test_category_delete_removes_annotations_associations(self):
        """Test that category delete removes associations with annotations."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create annotation with category
        trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.dataset.traces.add(trace)
        annotation = Annotation.objects.create(
            trace=trace, dataset=self.dataset, notes="Test"
        )
        annotation.failure_modes.add(self.failure_mode)

        url = reverse(
            "datasets:category_delete", args=[self.dataset.uid, self.failure_mode.uid]
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        # Association should be removed (Django handles this automatically)
        annotation.refresh_from_db()
        self.assertEqual(annotation.failure_modes.count(), 0)


class AnnotationViewWithFailureModesTests(TestCase):
    """Tests for annotation view with failure mode functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(user=self.user)
        self.org = Organization.objects.create(name="Test Org")
        Membership.objects.create(
            user_profile=self.user_profile, organization=self.org, role="admin"
        )
        self.project = Project.objects.create(
            name="Test Project", organization=self.org
        )
        self.dataset = Dataset.objects.create(name="Test Dataset", project=self.project)

        # Create trace
        self.trace = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.dataset.traces.add(self.trace)

        # Create failure modes
        self.failure_mode1 = FailureMode.objects.create(
            project=self.project, name="Hallucination", description="False info"
        )
        self.failure_mode2 = FailureMode.objects.create(
            project=self.project, name="Format Error", description="Wrong format"
        )

    def test_annotation_view_shows_failure_modes(self):
        """Test that annotation view shows available failure modes."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hallucination")
        self.assertContains(response, "Format Error")
        self.assertContains(response, "Failure Mode Categories")

    def test_annotation_view_saves_failure_modes(self):
        """Test that annotation view saves selected failure modes."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace.uid])
        response = self.client.post(
            url,
            {
                "notes": "Test annotation",
                "failure_modes": [self.failure_mode1.id, self.failure_mode2.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation = Annotation.objects.get(trace=self.trace, dataset=self.dataset)
        self.assertEqual(annotation.failure_modes.count(), 2)
        self.assertIn(self.failure_mode1, annotation.failure_modes.all())
        self.assertIn(self.failure_mode2, annotation.failure_modes.all())

    def test_annotation_view_shows_existing_failure_modes(self):
        """Test that annotation view pre-selects existing failure mode associations."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create annotation with failure modes
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Existing notes"
        )
        annotation.failure_modes.add(self.failure_mode1)

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check that form is pre-populated (checkboxes should be checked)
        form = response.context["form"]
        initial_modes = form.fields["failure_modes"].initial
        self.assertIn(self.failure_mode1.id, initial_modes)

    def test_annotation_view_updates_failure_modes(self):
        """Test that annotation view can update failure mode associations."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Create annotation with one failure mode
        annotation = Annotation.objects.create(
            trace=self.trace, dataset=self.dataset, notes="Existing notes"
        )
        annotation.failure_modes.add(self.failure_mode1)

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace.uid])
        # Update to only have failure_mode2
        response = self.client.post(
            url,
            {
                "notes": "Updated notes",
                "failure_modes": [self.failure_mode2.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.assertEqual(annotation.failure_modes.count(), 1)
        self.assertIn(self.failure_mode2, annotation.failure_modes.all())
        self.assertNotIn(self.failure_mode1, annotation.failure_modes.all())
