from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.utils import timezone
from accounts.models import UserProfile, Organization, Membership
from projects.models import Project
from traces.models import Trace
from datasets.models import Dataset

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
        dataset1 = Dataset.objects.create(name="Dataset 1", project=self.project)
        dataset2 = Dataset.objects.create(name="Dataset 2", project=self.project)

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
