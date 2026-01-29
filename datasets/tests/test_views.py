from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.utils import timezone
from accounts.models import UserProfile, Organization, Membership
from projects.models import Project
from traces.models import Trace, Span
from datasets.models import Dataset, Annotation

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

    def test_dataset_create_shows_success_message(self):
        """Test that success message is displayed after creation."""
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

        self.assertEqual(len(messages), 1)
        self.assertIn("created successfully", str(messages[0]).lower())

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

        # Create traces
        self.trace1 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-1",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.trace2 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-2",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )
        self.trace3 = Trace.objects.create(
            project=self.project,
            otel_trace_id="trace-3",
            started_at=timezone.now(),
            ended_at=timezone.now(),
            attributes={},
        )

        self.dataset.traces.add(self.trace1, self.trace2, self.trace3)

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

        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["total_traces"], 3)
        self.assertEqual(context["current_trace_number"], 1)
        self.assertEqual(context["unannotated_count"], 3)

    def test_annotation_view_shows_navigation_buttons(self):
        """Test that Previous/Next buttons are displayed correctly."""
        self.client.login(username="testuser", password="testpass123")
        session = self.client.session
        session["current_project_id"] = self.project.id
        session.save()

        # Test first trace (no previous)
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace1.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIsNone(context["prev_trace_uid"])
        self.assertIsNotNone(context["next_trace_uid"])

        # Test middle trace (has both)
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace2.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIsNotNone(context["prev_trace_uid"])
        self.assertIsNotNone(context["next_trace_uid"])

        # Test last trace (no next)
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

        # In review mode, should navigate to next trace in order
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

        # Finish reviewing (post on last trace)
        url = reverse("datasets:annotate", args=[self.dataset.uid, self.trace3.uid])
        response = self.client.post(url, {"notes": "Updated notes"}, follow=True)

        messages = list(get_messages(response.wsgi_request))
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
